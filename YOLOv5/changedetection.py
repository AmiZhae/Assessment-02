import os
import time
import uuid
import sqlite3
import threading
import getpass
from datetime import datetime
from pathlib import Path

import cv2
import requests
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent / ".env")

class ChangeDetection:
    def __init__(self, names):
        self.names = names
        self.result_prev = [0] * len(names)
        self.missing_frames = [0] * len(names)
        self.last_upload = {}

        self.absence_threshold = max(
            1,
            int(os.environ.get("DETECTION_ABSENCE_FRAMES", "5"))
        )

        self.cooldown = max(
            0,
            float(os.environ.get("DETECTION_COOLDOWN", "30"))
        )

        self.host = os.environ.get(
            "DJANGO_HOST",
            "http://127.0.0.1:8000"
        ).strip().rstrip("/")

        self.username = os.environ.get(
            "DJANGO_USERNAME", ""
        ).strip()

        self.password = os.environ.get("DJANGO_PASSWORD", "")
        if not self.password and self.username:
            self.password = getpass.getpass(
                "Enter your Django password: "
                )

        self.token = os.environ.get(
            "DJANGO_TOKEN", ""
        ).strip()

        if not self.host.startswith(("http://", "https://")):
            raise ValueError(
                "DJANGO_HOST must start with http:// or https://"
            )

        # Store the queue outside the YOLOv5 runs folder.
        # This allows detections to survive application restarts.
        self.base_dir = Path(__file__).resolve().parent
        self.queue_dir = self.base_dir / "offline_queue"
        self.image_dir = self.queue_dir / "images"
        self.db_path = self.queue_dir / "queue.db"

        self.image_dir.mkdir(
            parents=True,
            exist_ok=True
        )

        self.db_lock = threading.Lock()
        self.stop_event = threading.Event()
        self.wake_event = threading.Event()

        # Keep network work in the background.
        self.session = requests.Session()

        self.init_database()

        print("=" * 55)
        print("[SYSTEM] YOLOv5 Offline Detection Uploader")
        print(f"[SERVER] {self.host}")
        print(f"[QUEUE] {self.db_path}")
        print(f"[STABILITY] {self.absence_threshold} frames")
        print(f"[COOLDOWN] {self.cooldown} seconds")
        print("=" * 55)

        # Start the uploader immediately.
        # Authentication and network errors will be
        # handled by the worker without stopping YOLOv5.
        self.worker = threading.Thread(
            target=self.upload_worker,
            daemon=True,
            name="DetectionUploadWorker"
        )
        self.worker.start()

        print("[WORKER] Background uploader started")
        print(f"[QUEUE] Pending: {self.pending_count()}")

    def connect_database(self):
        connection = sqlite3.connect(
            str(self.db_path),
            timeout=15
        )
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA busy_timeout = 15000")
        return connection

    def init_database(self):
        with self.db_lock:
            with self.connect_database() as db:
                db.execute("""
                    CREATE TABLE IF NOT EXISTS uploads (
                        event_id TEXT PRIMARY KEY,
                        title TEXT NOT NULL,
                        description TEXT NOT NULL,
                        image_path TEXT NOT NULL,
                        created_at TEXT NOT NULL,
                        status TEXT NOT NULL DEFAULT 'pending',
                        attempts INTEGER NOT NULL DEFAULT 0,
                        next_retry REAL NOT NULL DEFAULT 0,
                        last_error TEXT
                    )
                """)

                db.execute("""
                    CREATE INDEX IF NOT EXISTS
                    idx_uploads_retry
                    ON uploads(status, next_retry)
                """)

                # If an earlier run was interrupted,
                # recover anything not yet completed.
                db.execute("""
                    UPDATE uploads
                    SET status = 'pending',
                        next_retry = 0
                    WHERE status = 'uploading'
                """)

                db.commit()

    def pending_count(self):
        with self.db_lock:
            with self.connect_database() as db:
                row = db.execute("""
                    SELECT COUNT(*) AS total
                    FROM uploads
                    WHERE status != 'uploaded'
                """).fetchone()

                return row["total"]

    def authenticate(self):
        if self.token:
            return True

        if not self.username or not self.password:
            print(
                "[AUTH] Missing DJANGO_USERNAME "
                "or DJANGO_PASSWORD"
            )
            return False

        try:
            print("[AUTH] Connecting to Django...")

            response = self.session.post(
                f"{self.host}/api-token-auth/",
                data={
                    "username": self.username,
                    "password": self.password
                },
                timeout=10
            )

            response.raise_for_status()
            self.token = response.json()["token"]

            print("[AUTH] Authentication successful")
            return True

        except (requests.RequestException, KeyError, ValueError) as exc:
            print(f"[AUTH FAILED] {exc}")
            return False

    def add(self, names, detected_current, save_dir, image):
        now = time.monotonic()
        new_objects = []

        # All categories currently detected in this frame.
        visible_objects = [
            str(names[i])
            for i, detected in enumerate(detected_current)
            if detected == 1
        ]

        for i in range(len(self.result_prev)):
            currently_detected = detected_current[i] == 1
            was_active = self.result_prev[i] == 1

            if currently_detected:
                self.missing_frames[i] = 0

                if not was_active:
                    self.result_prev[i] = 1

                    object_name = str(names[i])
                    last_time = self.last_upload.get(object_name)

                    if (
                        last_time is not None
                        and now - last_time < self.cooldown
                    ):
                        remaining = self.cooldown - (
                            now - last_time
                        )

                        print(
                            f"[COOLDOWN] {object_name}: "
                            f"{remaining:.1f}s remaining"
                        )
                    else:
                        new_objects.append(object_name)

            else:
                if was_active:
                    self.missing_frames[i] += 1

                    if (
                        self.missing_frames[i]
                        >= self.absence_threshold
                    ):
                        self.result_prev[i] = 0
                        self.missing_frames[i] = 0

                        print(
                            f"[RESET] {names[i]} absent for "
                            f"{self.absence_threshold} frames"
                        )

        if not new_objects:
            return

        title = new_objects[0]

        # Include ALL visible categories, including title.
        description = ", ".join(visible_objects)

        print("-" * 55)
        print(f"[DETECTION] {title}")
        print(f"[DESCRIPTION] {description}")

        # Save detection and register it in SQLite.
        # This does not make a network request.
        queued = self.queue_detection(
            image=image,
            title=title,
            description=description
        )

        if queued:
            for object_name in new_objects:
                self.last_upload[object_name] = now

    def queue_detection(self, image, title, description):
        event_id = str(uuid.uuid4())
        created_at = datetime.now().astimezone().isoformat()

        filename = f"{event_id}.jpg"
        image_path = self.image_dir / filename

        try:
            resized_image = cv2.resize(
                image,
                (320, 240),
                interpolation=cv2.INTER_AREA
            )

            if not cv2.imwrite(
                str(image_path),
                resized_image
            ):
                print("[QUEUE ERROR] Cannot save image")
                return False

            with self.db_lock:
                with self.connect_database() as db:
                    db.execute("""
                        INSERT INTO uploads (
                            event_id,
                            title,
                            description,
                            image_path,
                            created_at,
                            status,
                            attempts,
                            next_retry
                        )
                        VALUES (?, ?, ?, ?, ?, 'pending', 0, 0)
                    """, (
                        event_id,
                        title,
                        description,
                        str(image_path),
                        created_at
                    ))

                    db.commit()

            print(f"[SAVED] {image_path}")
            print(f"[QUEUED] Event ID: {event_id}")
            print(f"[QUEUE] Pending: {self.pending_count()}")

            # Wake the background worker.
            self.wake_event.set()
            return True

        except (OSError, sqlite3.Error, cv2.error) as exc:
            print(f"[QUEUE ERROR] {exc}")

            # Remove an image that was saved but never queued.
            try:
                image_path.unlink(missing_ok=True)
            except OSError:
                pass

            return False

    def next_upload(self):
        with self.db_lock:
            with self.connect_database() as db:
                row = db.execute("""
                    SELECT *
                    FROM uploads
                    WHERE status = 'pending'
                      AND next_retry <= ?
                    ORDER BY created_at ASC
                    LIMIT 1
                """, (time.time(),)).fetchone()

                if row is None:
                    return None

                db.execute("""
                    UPDATE uploads
                    SET status = 'uploading'
                    WHERE event_id = ?
                """, (row["event_id"],))

                db.commit()
                return dict(row)

    def mark_uploaded(self, event_id):
        with self.db_lock:
            with self.connect_database() as db:
                db.execute("""
                    UPDATE uploads
                    SET status = 'uploaded',
                        last_error = NULL
                    WHERE event_id = ?
                """, (event_id,))

                db.commit()

    def mark_failed(self, record, error):
        attempts = record["attempts"] + 1

        # Exponential backoff capped at 60 seconds.
        # 5, 10, 20, 40, 60, 60...
        delay = min(60, 5 * (2 ** min(attempts - 1, 4)))
        next_retry = time.time() + delay

        with self.db_lock:
            with self.connect_database() as db:
                db.execute("""
                    UPDATE uploads
                    SET status = 'pending',
                        attempts = ?,
                        next_retry = ?,
                        last_error = ?
                    WHERE event_id = ?
                """, (
                    attempts,
                    next_retry,
                    str(error)[:1000],
                    record["event_id"]
                ))

                db.commit()

        print(
            f"[RETRY] {record['event_id']} "
            f"will retry in {delay}s"
        )

    def upload_record(self, record):
        event_id = record["event_id"]
        image_path = Path(record["image_path"])

        if not image_path.is_file():
            self.mark_failed(
                record,
                "Image file missing"
            )
            return

        if not self.authenticate():
            self.mark_failed(
                record,
                "Authentication unavailable"
            )
            return

        headers = {
            "Authorization": f"Token {self.token}",
            "Accept": "application/json"
        }

        data = {
            "event_id": event_id,
            "title": record["title"],
            "text": record["description"]
        }

        try:
            print(f"[UPLOAD] Sending {event_id}")

            with image_path.open("rb") as image_file:
                response = self.session.post(
                    f"{self.host}/api_root/Post/",
                    data=data,
                    files={
                        "image": (
                            image_path.name,
                            image_file,
                            "image/jpeg"
                        )
                    },
                    headers=headers,
                    timeout=15
                )

            # Django returns:
            # 201 = newly created
            # 200 = event already exists (safe retry)
            if response.status_code in (200, 201):
                body = response.json()

                # Require confirmation of the same event ID.
                if str(body.get("event_id")) != event_id:
                    raise ValueError(
                        "Server returned a different event_id"
                    )

                self.mark_uploaded(event_id)

                print(
                    f"[SUCCESS] HTTP {response.status_code} "
                    f"- {record['title']}"
                )
                print(f"[QUEUE] Pending: {self.pending_count()}")
                return

            if response.status_code == 401:
                # Refresh the token on a future attempt.
                if self.username and self.password:
                    self.token = ""

            response.raise_for_status()

            raise ValueError(
                f"Unexpected HTTP {response.status_code}"
            )

        except (
            requests.RequestException,
            ValueError,
            OSError
        ) as exc:
            print(f"[UPLOAD FAILED] {exc}")
            self.mark_failed(record, exc)

    def upload_worker(self):
        while not self.stop_event.is_set():
            try:
                record = self.next_upload()

                if record is not None:
                    self.upload_record(record)
                    continue

                # No due uploads. Wait briefly or until
                # a new detection wakes the worker.
                self.wake_event.wait(timeout=2)
                self.wake_event.clear()

            except Exception as exc:
                # Keep the worker alive on unexpected errors.
                print(f"[WORKER ERROR] {exc}")
                self.stop_event.wait(timeout=5)

        print("[WORKER] Stopped")

    def close(self):
        self.stop_event.set()
        self.wake_event.set()

        if self.worker.is_alive():
            self.worker.join(timeout=3)

        self.session.close()

        print(
            f"[QUEUE] Remaining uploads: "
            f"{self.pending_count()}"
        )
