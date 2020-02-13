from typing import TYPE_CHECKING, Optional

from qactuar.child_process import ChildProcess
from qactuar.models import Message, Scope

if TYPE_CHECKING:
    from qactuar import QactuarServer

ASGI_VERSION = {"version": "2.0", "spec_version": "2.0"}


class Handler:
    def __init__(self, server: "QactuarServer"):
        self.server = server
        self.child: Optional[ChildProcess] = None

    def set_child(self, child: ChildProcess) -> None:
        self.child = child


class HTTPHandler(Handler):
    def create_scope(self) -> Scope:
        # TODO: Pseudo headers (present in HTTP/2 and HTTP/3) must be removed; if
        #  :authority is present its value must be added to the start of the iterable
        #  with host as the header name or replace any existing host header already
        #  present.
        if self.child:
            return {
                "type": "http",
                "asgi": ASGI_VERSION,
                "http_version": self.child.request_data.request_version_num,
                "method": self.child.request_data.method,
                "scheme": self.server.scheme,
                "path": self.child.request_data.path,
                "raw_path": self.child.request_data.raw_path,
                "query_string": self.child.request_data.query_string,
                "root_path": "",
                "headers": self.child.request_data.raw_headers,
                "client": self.server.client_info,
                "server": (self.server.server_name, self.server.server_port),
            }
        else:
            raise AttributeError

    async def receive(self) -> Message:
        # TODO: support streaming from client
        if self.child:
            return {
                "type": "http.request",
                "body": self.child.request_data.body,
                "more_body": False,
            }
        else:
            raise AttributeError

    async def send(self, data: Message) -> None:
        if self.child:
            if data["type"] == "http.response.start":
                self.child.response.status = str(data["status"]).encode("utf-8")
                self.child.response.headers += data["headers"]
            if data["type"] == "http.response.body":
                # TODO: check "more_body" and if true then do
                #  self.server.client_connection.send() to send the current data
                self.child.response.body.write(data["body"])
        else:
            raise AttributeError


class WebSocketHandler(Handler):
    def ws_shake_hand(self) -> None:
        pass

    def create_websocket(self) -> None:
        pass

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
