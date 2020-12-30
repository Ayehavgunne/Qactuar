from base64 import standard_b64encode
from hashlib import sha1
from typing import TYPE_CHECKING

from qactuar.models import Message, Scope
from qactuar.request import Request
from qactuar.response import Response

if TYPE_CHECKING:
    from qactuar.servers.base import BaseQactuarServer

ASGI_VERSION = {"version": "2.0", "spec_version": "2.0"}
MAGIC_STRING = b"258EAFA5-E914-47DA-95CA-C5AB0DC85B11"


class Handler:
    def __init__(self, server: "BaseQactuarServer"):
        self.server = server
        self._request: Request = Request()
        self._response: Response = Response(request=self._request)
        self.closing = False

    @property
    def request(self) -> Request:
        return self._request

    @request.setter
    def request(self, request: Request) -> None:
        self._request = request
        self._response.request = request

    @property
    def response(self) -> Response:
        return self._response

    @response.setter
    def response(self, response: Response) -> None:
        self._response = response
        self._response.request = self._request


class HTTPHandler(Handler):
    def create_scope(self) -> Scope:
        # TODO: Pseudo headers (present in HTTP/2 and HTTP/3) must be removed; if
        #  :authority is present its value must be added to the start of the iterable
        #  with host as the header name or replace any existing host header already
        #  present.
        return {
            "type": "http",
            "asgi": ASGI_VERSION,
            "http_version": self.request.request_version_num,
            "method": self.request.method,
            "scheme": self.server.scheme,
            "path": self.request.path,
            "raw_path": self.request.raw_path,
            "query_string": self.request.query_string,
            "root_path": "",
            "headers": self.request.raw_headers,
            "client": self.server.client_info,
            "server": (self.server.server_name, self.server.server_port),
        }

    async def receive(self) -> Message:
        # TODO: support streaming from client
        if self.closing:
            return {
                "type": "http.disconnect",
            }
        else:
            return {
                "type": "http.request",
                "body": self.request.body,
                "more_body": False,
            }

    async def send(self, data: Message) -> None:
        if data["type"] == "http.response.start":
            self.response.status = str(data["status"]).encode("utf-8")
            self.response.headers += data["headers"]
        if data["type"] == "http.response.body":
            # TODO: check "more_body" and if true then do
            #  self.server.client_connection.send() to send the current data
            self.response.body.write(data["body"])


class WebSocketHandler(Handler):
    def ws_shake_hand(self) -> None:
        websocket_key = self.request.headers["sec-websocket-key"]
        if websocket_key:
            websocket_accept = standard_b64encode(
                sha1(websocket_key.encode("utf-8") + MAGIC_STRING).digest()
            )
            self.response.status = b"101 Switching Protocols"
            self.response.add_header("Upgrade", "websocket")
            self.response.add_header("Connection", "Upgrade")
            self.response.add_header("Sec-WebSocket-Accept", websocket_accept)

    def send(self, data: Message) -> None:
        pass


class LifespanHandler(Handler):
    @staticmethod
    def create_scope() -> Scope:
        return {"type": "lifespan", "asgi": ASGI_VERSION}

    async def receive(self) -> Message:
        return {
            "type": "lifespan.startup"
            if not self.server.shutting_down
            else "lifespan.shutdown",
            "asgi": ASGI_VERSION,
        }

    async def send(self, data: Message) -> None:
        if (
            data["type"] == "lifespan.startup.failed"
            or data["type"] == "lifespan.shutdown.failed"
        ):
            if "startup" in data["type"]:
                self.server.server_log.error("App startup failed")
            if "shutdown" in data["type"]:
                self.server.server_log.error("App shutdown failed")
            self.server.server_log.error(data["message"])
