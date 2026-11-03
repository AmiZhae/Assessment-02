
import os
import cv2
import pathlib
import requests
from datetime import datetime


class ChangeDetection:
    result_prev = []
    HOST = 'http://127.0.0.1:8000'
    username = os.environ.get('DJANGO_USERNAME', '')
    password =  os.environ.get('DJANGO_PASSWORD', '')
    token = ''
    title = ''
    text = ''

    def __init__(self, names):
        self.result_prev = [0 for i in range(len(names))]

        # Authenticate with Django REST API
        res = requests.post(
            self.HOST + '/api-token-auth/',
            {
                'username': self.username,
                'password': self.password
            },
            timeout=10
        )

        res.raise_for_status()
        self.token = res.json()['token']
        print("Django authentication successful")

    def add(self, names, detected_current, save_dir, image):
        self.title = ''
        self.text = ''
        change_flag = 0  # Change detection flag

        i = 0
        while i < len(self.result_prev):
            if self.result_prev[i] == 0 and detected_current[i] == 1:
                change_flag = 1
                self.title = names[i]
                self.text += names[i] + ", "
            i += 1

        # Save current detection state
        self.result_prev = detected_current[:]

        if change_flag == 1:
            self.send(save_dir, image)

    def send(self, save_dir, image):
        now = datetime.now()

        today = datetime.now()
        save_path = (
            pathlib.Path(os.getcwd())
            / save_dir
            / 'detected'
            / str(today.year)
            / str(today.month)
            / str(today.day)
        )

        pathlib.Path(save_path).mkdir(
            parents=True,
            exist_ok=True
        )

        full_path = save_path / '{0}-{1}-{2}-{3}.jpg'.format(
            today.hour,
            today.minute,
            today.second,
            today.microsecond
        )

        dst = cv2.resize(
            image,
            dsize=(320, 240),
            interpolation=cv2.INTER_AREA
        )

        cv2.imwrite(str(full_path), dst)

        # Django REST Framework token authentication
        headers = {
            'Authorization': 'Token ' + self.token,
            'Accept': 'application/json'
        }

        # Create blog post
        data = {
            'title': self.title,
            'text': self.text,
            'created_date': now.isoformat(),
            'published_date': now.isoformat()
        }

        with open(full_path, 'rb') as image_file:
            files = {'image': image_file}

            res = requests.post(
                self.HOST + '/api_root/Post/',
                data=data,
                files=files,
                headers=headers,
                timeout=15
            )

        print("Django upload response:", res.status_code)
        res.raise_for_status()
