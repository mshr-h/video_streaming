import cv2
import os
import threading
import redis
import numpy as np
import time


class VideoRecorder(object):
    def __init__(self, src=-1, width=None, height=None):
        video = cv2.VideoCapture(src)
        if not video.isOpened():
            raise RuntimeError("VideoCapture({}) could not open.".format(src))
        video.set(3, width)
        video.set(4, height)
        self.video = video
        self.store = redis.Redis()
        self.running = False

    def __del__(self):
        if self.video.isOpened():
            self.video.release()

    def release(self):
        self.running = False
        self.video.release()

    def start_record(self):
        self.running = True
        thread = threading.Thread(target=self.update, daemon=True)
        thread.start()
        return self

    def update(self):
        while self.running:
            _, image = self.video.read()
            if image is None:
                time.sleep(0.3)
                continue
            _, image = cv2.imencode('.png', image)
            image_np = np.array(image).tobytes()
            self.store.set('image', image_np)
            image_id = os.urandom(4)
            self.store.set('image_id', image_id)
