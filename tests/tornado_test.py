from tornado.web import RequestHandler

from qactuar.util import TornadoWrapper


# noinspection PyAbstractClass
class HelloWorld(RequestHandler):
    def get(self):
        self.write("Hello, WORLD!")


app = TornadoWrapper(HelloWorld)
