import asyncio
import os
import socket
import ssl
from logging import getLogger
from random import randint
from time import sleep, time
from typing import TYPE_CHECKING

from qactuar.exceptions import HTTPError
from qactuar.handlers import HTTPHandler, WebSocketHandler
from qactuar.request import Request
from qactuar.response import Response
from qactuar.util import BytesList
from qactuar.websocket import Frame, WebSocket

if TYPE_CHECKING:
    from qactuar import ASGIApp
    from qactuar.servers.base import BaseQactuarServer


class BaseProcessHandler:
    def __init__(self, server: "BaseQactuarServer"):
        self.loop = asyncio.new_event_loop()
        self.server = server
        self.child_log = getLogger("qt_child")
        self._access_log = getLogger("qt_access")
        self.exception_log = getLogger("qt_exception")

    def get_app(self, request: Request) -> "ASGIApp":
        current_path = request.path
        for route, app in self.server.apps.items():
            if route == "/":
                if current_path == route:
                    return app
            elif current_path.startswith(route):
                request.path = current_path.replace(route, "")
                return app
        try:
            app = self.server.apps["/"]
        except KeyError:
            raise HTTPError(404)
        else:
            return app

    def setup_ssl(self, client_socket: socket.socket) -> socket.socket:
        if self.server.ssl_context:
            ssl_socket = self.server.ssl_context.wrap_socket(
                client_socket, server_side=True, do_handshake_on_connect=False
            )
            try:
                ssl_socket.do_handshake()
            except ssl.SSLError as err:
                if err.args[1].find("sslv3 alert") == -1:
                    self.exception_log.exception(err)
                    raise HTTPError(403)
                else:
                    client_socket = ssl_socket
            else:
                client_socket = ssl_socket
            client_socket.settimeout(self.server.config.RECV_TIMEOUT)
        else:
            client_socket.settimeout(self.server.config.RECV_TIMEOUT)
        return client_socket

    def log_access(self, request: Request, response: Response) -> None:
        self._access_log.info(
            "",
            extra={
                "host": self.server.client_info[0],
                "port": self.server.client_info[1],
                "pid": os.getpid(),
                "request_id": request.request_id,
                "method": request.method,
                "http_version": request.request_version_num,
                "path": request.original_path or "/",
                "status": response.status.decode("utf-8"),
            },
        )

    async def handle_request(self, client_socket: socket.socket) -> None:
        request = await self.get_request_data(client_socket)
        http_handler = HTTPHandler(self.server, request)
        if not request.raw_request:
            await self.close_socket(client_socket, http_handler)
            return
        try:
            if (
                request.headers["connection"] == "Upgrade"
                and request.headers["upgrade"] == "websocket"
            ):
                websocket_handler = WebSocketHandler(self.server, request)
                websocket_handler.ws_shake_hand()
                client_socket.sendall(http_handler.response.to_http())
                self.log_access(request, http_handler.response)
                self.start_websocket(client_socket, http_handler)
                http_handler.response.clear()
                return
            await self.send_to_app(http_handler)
        except HTTPError as err:
            http_handler.response.status = str(err.args[0]).encode("utf-8")
            http_handler.response.body.write(str(err.args[0]).encode("utf-8"))
        except Exception as err:
            self.exception_log.exception(err, extra={"request_id": request.request_id})
            http_handler.response.status = b"500"
            http_handler.response.body.write(b"Internal Server Error")
        finally:
            if http_handler.response:
                self.log_access(request, http_handler.response)
            await self.finish_response(client_socket, http_handler)

    async def get_request_data(self, client_socket: socket.socket) -> Request:
        request_data = BytesList()
        request = Request()
        start = time()

        while True:
            try:
                request_data.write(client_socket.recv(self.server.config.RECV_BYTES))
            except socket.timeout:
                if not len(request_data):
                    if time() - start > self.server.config.REQUEST_TIMEOUT:
                        self.child_log.debug(
                            "no data received from request, timing out"
                        )
                        break
            request.raw_request = request_data.read()
            if request.headers_complete:
                content_length = request.headers["content-length"]
                if content_length is not None and request.method != "GET":
                    if len(request.body) == int(content_length):
                        break
                    else:
                        continue
                break

        return request

    async def send_to_app(self, http_handler: HTTPHandler) -> None:
        app = self.get_app(http_handler.request)
        await app(
            http_handler.create_scope(),
            http_handler.receive,
            http_handler.send,
        )

    def start_websocket(
        self, client_socket: socket.socket, http_handler: HTTPHandler
    ) -> None:
        websocket = WebSocket()
        frame = self.get_websocket_frame(client_socket)
        websocket.add_read_frame(frame)
        while True:
            self.websocket_read(websocket, client_socket)
            if websocket.should_terminate:
                self.close_socket(client_socket, http_handler)
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

    async def finish_response(
        self, client_socket: socket.socket, http_handler: HTTPHandler
    ) -> None:
        try:
            if http_handler.response:
                http_handler.response.add_header(
                    "x-request-id", http_handler.request.request_id
                )
                client_socket.sendall(http_handler.response.to_http())
        except OSError as err:
            self.exception_log.exception(
                err, extra={"request_id": http_handler.request.request_id}
            )
        await self.close_socket(client_socket, http_handler)

    async def close_socket(
        self, client_socket: socket.socket, http_handler: HTTPHandler
    ) -> None:
        http_handler.closing = True
        try:
            await self.send_to_app(http_handler)
        except HTTPError:
            pass
        client_socket.close()

    async def start(self) -> None:
        raise NotImplementedError
