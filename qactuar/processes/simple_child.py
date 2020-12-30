import socket
import sys
from logging import Logger, getLogger
from random import randint
from time import sleep
from typing import TYPE_CHECKING

from qactuar.exceptions import HTTPError
from qactuar.handlers import HTTPHandler, WebSocketHandler
from qactuar.processes.base import BaseProcessHandler
from qactuar.request import Request
from qactuar.response import Response
from qactuar.util import BytesList
from qactuar.websocket import Frame, WebSocket

if TYPE_CHECKING:
    from qactuar.servers.base import BaseQactuarServer


class ChildProcess(BaseProcessHandler):
    def __init__(self, server: "BaseQactuarServer"):
        super().__init__(server)
        self.stats_log: Logger = getLogger("qt_stats")
        self.http_handler = HTTPHandler(server)
        self.websocket_handler = WebSocketHandler(server)

    def start(self, client_socket: socket.socket = None) -> None:
        if not client_socket:
            return
        if self.server.ssl_context is not None:
            client_socket = self.setup_ssl(client_socket)
        else:
            client_socket.settimeout(self.server.config.RECV_TIMEOUT)
        request = self.get_request_data(client_socket)
        self.http_handler.request = request
        try:
            self.handle_request(client_socket, request)
        except KeyboardInterrupt:
            sys.exit(0)
        except HTTPError as err:
            self.http_handler.response.status = str(err.args[0]).encode("utf-8")
            self.http_handler.response.body.write(str(err.args[0]).encode("utf-8"))
        except Exception as err:
            self.exception_log.exception(err, extra={"request_id": request.request_id})
            self.http_handler.response.status = b"500"
            self.http_handler.response.body.write(b"Internal Server Error")
        finally:
            if self.http_handler.response:
                self.log_access(request, self.http_handler.response)
            self.finish_response(client_socket, self.http_handler.response)

    def handle_request(
        self, client_socket: socket.socket, request: Request
    ) -> Response:
        if not request.raw_request:
            self.close_socket(client_socket, request)
            return self.http_handler.response
        if (
            request.headers["connection"] == "Upgrade"
            and request.headers["upgrade"] == "websocket"
        ):
            self.websocket_handler.ws_shake_hand()
            client_socket.sendall(self.http_handler.response.to_http())
            self.log_access(request, self.http_handler.response)
            self.start_websocket(client_socket, request)
            self.http_handler.response.clear()
            return self.http_handler.response
        return self.send_to_app(request)

    def send_to_app(self, request: Request) -> Response:
        self.loop.run_until_complete(
            self.get_app(request)(
                self.http_handler.create_scope(),
                self.http_handler.receive,
                self.http_handler.send,
            )
        )
        return self.http_handler.response

    def close_socket(self, client_socket: socket.socket, request: Request) -> None:
        self.http_handler.closing = True
        try:
            self.send_to_app(request)
        except HTTPError:
            pass
        super().close_socket(client_socket, request)

    def start_websocket(self, client_socket: socket.socket, request: Request) -> None:
        websocket = WebSocket()
        frame = self.get_websocket_frame(client_socket)
        websocket.add_read_frame(frame)
        while True:
            self.websocket_read(websocket, client_socket)
            if websocket.should_terminate:
                self.close_socket(client_socket, request)
                break
            if websocket.being_pinged:
                message = websocket.read()
                websocket.write(message or "", pong=True)
                response = websocket.response
                if response:
                    client_socket.sendall(response)
            if randint(0, 1):
                websocket.clear_frames()
                websocket.write("ping", ping=True)
                response = websocket.response
                if response:
                    client_socket.sendall(response)
                frame = self.get_websocket_frame(client_socket)
                if frame.is_pong and frame.message == "ping":
                    print("ponged")
                else:
                    print(frame.message)
            websocket.clear_frames()

    def websocket_read(
        self, websocket: WebSocket, client_socket: socket.socket
    ) -> None:
        while not websocket.reading_complete:
            frame = self.get_websocket_frame(client_socket)
            websocket.add_read_frame(frame)
        message = websocket.read()
        if message:  # TODO: send message to app and send app responses back
            sleep(1)
            websocket.write(message)
            try:
                response = websocket.response
                if response:
                    client_socket.sendall(response)
            except OSError as err:
                self.exception_log.exception(err)

    def get_websocket_frame(self, client_socket: socket.socket) -> Frame:
        request_data = BytesList()

        while True:
            try:
                request_data.write(client_socket.recv(self.server.config.RECV_BYTES))
            except socket.timeout:
                pass
            frame = Frame(request_data.read())
            if frame.is_complete:
                break
        return frame


def make_child(server: "BaseQactuarServer", client_socket: socket.socket) -> None:
    child = ChildProcess(server)
    child.start(client_socket)
