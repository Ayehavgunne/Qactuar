import asyncio
import socket
import ssl
from io import BytesIO
from logging import getLogger
from random import randint
from time import time
from typing import TYPE_CHECKING

from qactuar.exceptions import HTTPError, WebSocketError
from qactuar.handlers import HTTPHandler, WebSocketHandler, WebSocketState
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
        return client_socket

    def log_access(self, request: Request, response: Response) -> None:
        self._access_log.info(
            "",
            extra={
                "host": self.server.client_info[0],
                "port": self.server.client_info[1],
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
                await self.websocket_loop(client_socket, http_handler)
                # http_handler.response.clear()
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
                data = await self.loop.sock_recv(
                    client_socket, self.server.config.RECV_BYTES
                )
                request_data.write(data)
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

    async def websocket_loop(
        self, client_socket: socket.socket, http_handler: HTTPHandler
    ) -> None:
        websocket_handler = WebSocketHandler(self.server)
        websocket_handler.request = http_handler.request
        websocket_handler.response = http_handler.response
        websocket_handler.ws_shake_hand()
        app = self.get_app(websocket_handler.request)
        await app(
            websocket_handler.create_scope(),
            websocket_handler.receive,
            websocket_handler.send,
        )
        if websocket_handler.state == WebSocketState.ACCEPTED:
            await self.loop.sock_sendall(
                client_socket, websocket_handler.response.to_http()
            )
        else:
            raise HTTPError(403)
        websocket_handler.response.clear()
        self.log_access(websocket_handler.request, websocket_handler.response)
        websocket = WebSocket()
        websocket_handler.websocket = websocket
        while True:
            websocket.clear_frames()
            await self.websocket_read(websocket, client_socket)
            if websocket.should_terminate:
                await self.close_socket(client_socket, http_handler)
                websocket_handler.state = WebSocketState.DISCONNECTED
                await app(
                    websocket_handler.create_scope(),
                    websocket_handler.receive,
                    websocket_handler.send,
                )
                break
            if websocket.being_pinged:
                await self.send_websocket_pong(websocket, client_socket)
                continue

            await self.send_websocket_ping(websocket, client_socket)

    async def send_websocket_ping(
        self, websocket: WebSocket, client_socket: socket.socket
    ) -> None:
        if randint(0, 20):
            websocket.clear_frames()
            websocket.write("ping", ping=True)
            response = websocket.pop_write_frame()
            if response:
                await self.loop.sock_sendall(client_socket, response)
            frame = await self.get_websocket_frame(client_socket)
            if not frame.is_pong and frame.message != "ping":
                raise WebSocketError(
                    "Client didn't respond properly after being pinged"
                )

    async def send_websocket_pong(
        self, websocket: WebSocket, client_socket: socket.socket
    ) -> None:
        message = websocket.read()
        websocket.write(message or "", pong=True)
        response = websocket.pop_write_frame()
        if response:
            await self.loop.sock_sendall(client_socket, response)

    async def websocket_read(
        self, websocket: WebSocket, client_socket: socket.socket
    ) -> None:
        while not websocket.reading_complete:
            frame = await self.get_websocket_frame(client_socket)
            websocket.add_read_frame(frame)

    async def get_websocket_frame(self, client_socket: socket.socket) -> Frame:
        with BytesIO() as request_data:
            while True:
                try:
                    data = await self.loop.sock_recv(
                        client_socket, self.server.config.RECV_BYTES
                    )
                    request_data.write(data)
                except socket.timeout:
                    pass
                frame = Frame(request_data.getvalue())
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
                await self.loop.sock_sendall(
                    client_socket, http_handler.response.to_http()
                )
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
