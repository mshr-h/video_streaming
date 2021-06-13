from video_recorder import VideoRecorder
import pdb_attach
import time
import base64
import redis
import argparse
import signal

from tornado import websocket, web, ioloop

pdb_attach.listen(5000)

accect_ctlc = False


def signal_handler(signum, frame):
    global accect_ctlc
    accect_ctlc = True


def try_exit():
    global accect_ctlc
    if accect_ctlc:
        ioloop.IOLoop.instance().stop()


class IndexHandler(web.RequestHandler):
    def get(self):
        self.render('index.html')


class VideoHandler(websocket.WebSocketHandler):
    def __init__(self, *args, **kwargs):
        super(VideoHandler, self).__init__(*args, **kwargs)
        self.storage = redis.Redis()
        self.prev_image_id = None

    def on_message(self, message):
        while True:
            time.sleep(0.01)
            image_id = self.storage.get("image_id")
            if image_id != self.prev_image_id:
                self.prev_image_id = image_id
                break

        image = self.storage.get("image")
        image = base64.b64encode(image)
        image_class = self.storage.get("image_class").decode("utf-8")
        image_score = float(self.storage.get("image_score"))
        message = ",".join([str(image.decode()), str(image_class), str(image_score)])
        self.write_message(message)


def main(args: argparse.Namespace):
    signal.signal(signal.SIGINT, signal_handler)

    app = web.Application([
        (r'/', IndexHandler),
        (r'/ws', VideoHandler),
    ])

    recorder = VideoRecorder()
    recorder.start_record()

    app.listen(args.port)
    ioloop.PeriodicCallback(try_exit, 100).start()
    ioloop.IOLoop.instance().start()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Camera Server")
    parser.add_argument("--port",
                        type=int,
                        default=8080,
                        help="Run on the given port")
    parser.add_argument("--width", type=int, default=None, help="Vidoe width")
    parser.add_argument("--height",
                        type=int,
                        default=None,
                        help="Video height")
    args: argparse.Namespace = parser.parse_args()

    main(args)
