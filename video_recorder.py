import cv2
import os
import threading
import redis
import numpy as np
import time
import coils
import logging
import classify
import tflite_runtime.interpreter as tflite


def load_labels(path, encoding='utf-8'):
  with open(path, 'r', encoding=encoding) as f:
    lines = f.readlines()
    if not lines:
      return {}

    if lines[0].split(' ', maxsplit=1)[0].isdigit():
      pairs = [line.split(' ', maxsplit=1) for line in lines]
      return {int(index): label.strip() for index, label in pairs}
    else:
      return {index: line.strip() for index, line in enumerate(lines)}


class VideoRecorder(object):
    def __init__(self, src: int = -1, width: int = None, height: int = None):
        video = cv2.VideoCapture(src)
        if not video.isOpened():
            raise RuntimeError("VideoCapture({}) could not open.".format(src))
        video.set(3, width)
        video.set(4, height)
        self.video = video
        self.storage = redis.Redis()
        self.running = False

        self.fps = coils.RateTicker((1, 5))

        self.logger = logging.getLogger("VideoRecorder")
        self.handler = logging.StreamHandler()
        self.handler.setLevel(logging.DEBUG)
        self.logger.setLevel(logging.DEBUG)
        self.logger.addHandler(self.handler)
        self.logger.propagate = False

        # TODO: split inference engine into dedicated class
        self.labels = load_labels("models/imagenet_labels.txt")
        self.interpreter = tflite.Interpreter(
                model_path="models/mobilenet_v2_1.0_224_quant_edgetpu.tflite",
                experimental_delegates=[tflite.load_delegate("libedgetpu.so.1.0")])
        self.interpreter.allocate_tensors()
        self.interpreter_input_size = classify.input_size(self.interpreter)
        self.frame_count = 0

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
            # retrieve frame from camera
            _, image = self.video.read()
            if image is None:
                time.sleep(0.1)
                continue

            # inference
            if self.frame_count == 0:
                resize_image = cv2.resize(image, self.interpreter_input_size, interpolation=cv2.INTER_CUBIC)
                reshape_image = resize_image.reshape(224, 224, 3)
                image_np_expanded = np.expand_dims(reshape_image, axis=0)
                image_np_expanded = image_np_expanded.astype("uint8")
                classify.set_input(self.interpreter, image_np_expanded)
                self.interpreter.invoke()
                classes = classify.get_output(self.interpreter, 1, 0.0)
            if self.frame_count < 9:
                self.frame_count += 1
            else:
                self.frame_count = 0

            # store to redis storage
            _, image = cv2.imencode('.jpg', image)
            image_np = np.array(image).tobytes()
            self.storage.set('image', image_np)
            self.storage.set('image_id', os.urandom(2))
            self.storage.set('image_class', self.labels.get(classes[0].id))
            self.storage.set('image_score', str(classes[0].score))
            self.logger.debug("{:.2f} fps".format(*self.fps.tick()))
