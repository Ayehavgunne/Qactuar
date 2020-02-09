from typing import TYPE_CHECKING

from qactuar.models import Message, Scope

if TYPE_CHECKING:
    from qactuar import QactuarServer

ASGI_VERSION = {"version": "2.0", "spec_version": "2.0"}


class Handler:
    def __init__(self, server: "QactuarServer"):
        self.server = server

    async def send(self, data: Message) -> None:
        if data["type"] == "http.response.start":
            self.server.response.status = str(data["status"]).encode("utf-8")
            self.server.response.headers = data["headers"]
        if data["type"] == "http.response.body":
            # TODO: check "more_body" and if true then do
            #  self.server.client_connection.send() to send the current data
            self.server.response.body.write(data["body"])
        if (
            data["type"] == "lifespan.startup.failed"
            or data["type"] == "lifespan.shutdown.failed"
        ):
            if "startup" in data["type"]:
                self.server.logger.error("App startup failed")
            if "shutdown" in data["type"]:
                self.server.logger.error("App shutdown failed")
            self.server.logger.error(data["message"])


class HTTPHandler(Handler):
    def __init__(self, server: "QactuarServer"):
        super().__init__(server)

    def create_scope(self) -> Scope:
        # TODO: Pseudo headers (present in HTTP/2 and HTTP/3) must be removed; if
        #  :authority is present its value must be added to the start of the iterable
        #  with host as the header name or replace any existing host header already
        #  present.
        return {
            "type": "http",
            "asgi": ASGI_VERSION,
            "http_version": self.server.request_data.request_version_num,
            "method": self.server.request_data.command,
            "scheme": self.server.scheme,
            "path": self.server.request_data.path,
            "raw_path": self.server.request_data.raw_path,
            "query_string": self.server.request_data.query_string,
            "root_path": "",
            "headers": self.server.request_data.raw_headers,
            "client": self.server.client_info,
            "server": (self.server.server_name, self.server.server_port),
        }

    async def receive(self) -> Message:
        # TODO: support streaming from client
        return {
            "type": "http.request",
            "body": self.server.request_data.body,
            "more_body": False,
        }


class WebSocketHandler(Handler):
    def __init__(self, server: "QactuarServer"):
        super().__init__(server)

    def ws_shake_hand(self) -> None:
        pass

    def create_websocket(self) -> None:
        pass


class LifespanHandler(Handler):
    def __init__(self, server: "QactuarServer"):
        super().__init__(server)

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
