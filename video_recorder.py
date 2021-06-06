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

        self.fps = coils.RateTicker((1, 5))

        self.logger = logging.getLogger("VideoRecorder")
        self.handler = logging.StreamHandler()
        self.handler.setLevel(logging.DEBUG)
        self.logger.setLevel(logging.DEBUG)
        self.logger.addHandler(self.handler)
        self.logger.propagate = False

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
        self.logger.debug("recording thread started")
        return self

    def update(self):
        while self.running:
            _, image = self.video.read()
            if image is None:
                time.sleep(0.3)
                continue
            _, image = cv2.imencode('.png', image)
            image_np = np.array(image).tobytes()
            self.logger.debug("{:.2f} fps".format(*self.fps.tick()))
