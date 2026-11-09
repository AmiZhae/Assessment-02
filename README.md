# Intruder Detection System — Assessment 02

An intruder monitoring and image management system built using **YOLOv5, Django REST Framework, and Android (Kotlin)**.

The system detects objects in real time using a webcam, records meaningful detection events, uploads annotated images to a Django server, and displays the detection history through a web gallery and an Android application.

This project was developed for the **Mobile Web Service Project — 공통평가 02**.

## 1. Project Overview

The system consists of three main components:

1. **YOLOv5 Detection System** — Performs real-time object detection, filters repeated events, and uploads detection images.
2. **Django PhotoBlogServer** — Provides a REST API, stores detection records, and displays images in a web gallery.
3. **Android PhotoViewer** — Retrieves detection records from the server and displays images, titles, and descriptions.

The Django application is deployed on PythonAnywhere for remote access.

## 2. System Architecture

```text
               Webcam
                  |
                  v
          YOLOv5 Detection
                  |
                  v
          ChangeDetection
                  |
          +-------+-------+
          |               |
          v               v
    Event Filtering   Offline Queue
          |               |
          +-------+-------+
                  |
                  v
         Django REST API
                  |
                  v
          Django Database
                  |
          +-------+-------+
          |               |
          v               v
     Web Gallery     Android PhotoViewer
```

## 3. Technologies Used

| Component                  | Technology                       |
| -------------------------- | -------------------------------- |
| Object Detection           | YOLOv5, PyTorch, OpenCV          |
| Detection Event Processing | Python                           |
| Offline Queue              | SQLite                           |
| Backend                    | Django, Django REST Framework    |
| REST API                   | HTTP, JSON, Token Authentication |
| Cloud Deployment           | PythonAnywhere                   |
| Android Application        | Kotlin, Android Studio           |
| Version Control            | Git, GitHub                      |

## 4. Project Structure

```text
Assessment02/
|
|-- PhotoBlogServer/
|   |-- blog/
|   |-- mysite/
|   |-- manage.py
|   `-- requirements.txt
|
|-- PhotoViewer/
|   |-- app/
|   |   `-- src/
|   |       `-- main/
|   |-- gradle/
|   `-- settings.gradle.kts
|
|-- YOLOv5/
|   |-- detect.py
|   |-- changedetection.py
|   |-- models/
|   |-- utils/
|   `-- requirements.txt
|
|-- README.md
`-- 모바일웹서비스_프로젝트_공통평가_01_수행_결과_보고서 (.docx)
```

Generated files, virtual environments, private configuration files, local databases, and offline detection images are excluded from Git using `.gitignore`.

## 5. Main Features

### 5.1 Real-Time Object Detection

- Detects objects through a webcam using YOLOv5.
- Draws bounding boxes and class labels on detected objects.
- Processes object detection results frame by frame.
- Passes detected object categories to `ChangeDetection`.

### 5.2 Automatic Image Upload

- Captures annotated images when new detection events occur.
- Sends detection images to the Django REST API.
- Stores image records with titles and descriptions.
- Supports authenticated requests to the server.

### 5.3 Django REST API

- Provides endpoints for accessing detection records.
- Supports image uploads and retrieval.
- Stores image metadata and uploaded files.
- Allows the Android application to access detection history.

### 5.4 Web Image Gallery

- Displays uploaded detection images.
- Shows image titles and descriptions.
- Provides access to locally stored or cloud-hosted detection records.

### 5.5 Android PhotoViewer

- Retrieves image records from the Django REST API.
- Displays detection images in a scrollable list.
- Shows image titles and descriptions.
- Supports viewing detection records on Android devices.

## 6. Additional Features

Two additional features were implemented to improve reliability and reduce unnecessary uploads.

### Feature 1 — Smart Detection Event Filtering

YOLOv5 normally processes every webcam frame. Without filtering, the same detected object could trigger repeated uploads.

The `ChangeDetection` component reduces duplicate events using two mechanisms:

**Detection absence threshold**

An object category must remain absent for five consecutive frames before its detection state resets.

**Upload cooldown**

A 30-second cooldown prevents the same object category from generating repeated uploads too frequently.

Example:

```text
[DETECTION] chair detected
[COOLDOWN] chair: 23.6s remaining
[RESET] chair absent for 5 frames
```

Benefits:

- Reduces duplicate detection records.
- Saves server storage.
- Reduces unnecessary network requests.
- Produces a more meaningful detection history.

### Feature 2 — Offline SQLite Queue and Automatic Retry

Network interruptions may prevent detection images from reaching the Django server.

To prevent detection events from being lost, the system stores pending upload events in a local SQLite queue.

**How it works:**

1. YOLOv5 detects an object.
2. The annotated image and event metadata are saved locally.
3. The upload event is added to the SQLite queue.
4. A background worker attempts to upload the event.
5. If the upload fails, the event remains queued.
6. The worker retries with exponential backoff.
7. Successfully uploaded events are removed from the pending queue.

Retry delays increase progressively, up to a configured maximum:

```text
5s -> 10s -> 20s -> 40s -> 60s
```

Example successful upload:

```text
[AUTH] Authentication successful
[SUCCESS] HTTP 201
[QUEUE] Pending: 0
```

Additional reliability improvements include:

- Background upload processing.
- Automatic recovery after temporary connection failures.
- Unique event identifiers to help prevent duplicate records.
- Persistent pending events using SQLite.

## 7. Django REST API

### Local Server

```text
http://127.0.0.1:8000/
```

### Cloud Server

**Website:** https://amirulzharif.pythonanywhere.com/

**REST API:** https://amirulzharif.pythonanywhere.com/api_root/

**Image Records:** https://amirulzharif.pythonanywhere.com/api_root/Post/

The REST API provides detection records to the Android application and accepts authenticated image uploads.

## 8. Installation and Setup

### Requirements

- Python and pip
- Git
- Webcam
- Android Studio (for the Android application)
- Android device or emulator
- Network connection for cloud uploads

### Step 1 — Clone the Repository

```bash
git clone https://github.com/AmiZhae/Assessment-02.git
cd Assessment-02
```

### Step 2 — Set Up the Django Server

Navigate to the backend:

```bash
cd PhotoBlogServer
```

Create a Python virtual environment:

```bash
python -m venv venv
```

Activate it on Windows:

```powershell
.\venv\Scripts\Activate.ps1
```

Install dependencies:

```bash
pip install -r requirements.txt
```

Configure the required Django environment variables, database, and media settings for your environment.

Apply migrations:

```bash
python manage.py migrate
```

Create an administrator account if needed:

```bash
python manage.py createsuperuser
```

Start the server:

```bash
python manage.py runserver 0.0.0.0:8000
```

### Step 3 — Set Up YOLOv5

Open a new terminal and navigate to:

```bash
cd YOLOv5
```

Create and activate a Python environment if needed, then install dependencies:

```bash
pip install -r requirements.txt
```

Configure the Django server URL and authentication credentials using the environment settings supported by `changedetection.py`.

Run webcam detection:

```bash
python detect.py --weights yolov5s.pt --source 0 --view-img --nosave
```

The detector will open the webcam, identify objects, and process detection events.

### Step 4 — Run Android PhotoViewer

1. Open the `PhotoViewer` folder in Android Studio.
2. Allow Gradle synchronization to finish.
3. Configure the REST API base URL for the target server.
4. Connect an Android phone or start an emulator.
5. Build and run the application.
6. Refresh the image list to view detection records.

For a physical Android phone accessing a local Django server, use the computer's reachable local network IP address instead of `127.0.0.1`.

## 9. Testing

The project was tested through the following workflows:

| Test                                | Result |
| ----------------------------------- | ------ |
| YOLOv5 webcam object detection      | Passed |
| Detection event processing          | Passed |
| Smart event filtering               | Passed |
| Django local REST API               | Passed |
| Django local image gallery          | Passed |
| Android PhotoViewer image retrieval | Passed |
| PythonAnywhere REST API             | Passed |
| PythonAnywhere image gallery        | Passed |
| Offline upload queue and recovery   | Passed |

The Android application was tested using an emulator and a physical Android device.

## 10. Assessment Requirements

| No. | Requirement                         | Status    |
| --- | ----------------------------------- | --------- |
| 1   | Project folder structure            | Completed |
| 2   | GitHub repository                   | Completed |
| 3   | Original YOLOv5 detection execution | Completed |
| 4   | YOLOv5 code modification            | Completed |
| 5   | Local Django REST API               | Completed |
| 6   | Local Django image gallery          | Completed |
| 7   | Android PhotoViewer                 | Completed |
| 8   | PythonAnywhere REST API             | Completed |
| 9   | PythonAnywhere image gallery        | Completed |
| 10  | Additional features                 | Completed |

Supporting screenshots and implementation details are provided in the Assessment 02 report.

## 11. Security and Notes

- Do not commit `.env` files or authentication credentials.
- Keep Django secret keys and passwords outside source code.
- Local SQLite databases and queued detection images should not be committed.
- The cloud deployment requires appropriate configuration for media files and database access.
- This project is intended for educational demonstration.

## 12. Author

**AmiZhae**

GitHub: https://github.com/AmiZhae

Developed for the Mobile Web Service Project 2026 — 공통평가 02.
