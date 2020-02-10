from typing import Any

from tornado.httputil import HTTPServerRequest
from tornado.web import Application, RequestHandler

from qactuar.util import TornadoWrapper


# noinspection PyAbstractClass
class HelloWorld(RequestHandler):
    def __init__(
        self, application: Application, request: HTTPServerRequest, **kwargs: Any
    ):
        super().__init__(application, request, **kwargs)

    async def get(self) -> None:
        self.write("Hello, WORLD!")


app = TornadoWrapper(HelloWorld)
