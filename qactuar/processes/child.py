import multiprocessing
import socket
import ssl
from io import BytesIO
from logging import getLogger
from random import randint
from typing import TYPE_CHECKING, Optional

from qactuar.exceptions import HTTPError, WebSocketError
from qactuar.handlers import Handler, HTTPHandler, WebSocketHandler, WebSocketState
from qactuar.processes.base import BaseProcessHandler
from qactuar.websocket import Frame, WebSocket

try:
    import psutil  # type: ignore
except ImportError:
    psutil = None

if TYPE_CHECKING:
    from qactuar import QactuarServer, ASGIApp


class ChildProcess(BaseProcessHandler):
    def __init__(self, server: "QactuarServer", client_socket: ssl.SSLSocket):
        super().__init__(server, client_socket)
        del self.server.admin_queue
        self.http_handler: HTTPHandler = HTTPHandler(self)
        self.websocket_handler: WebSocketHandler = WebSocketHandler(self)
        self.stats_log = getLogger("qt_stats")
        self.closing = False
        self._app: Optional["ASGIApp"] = None

    @property
    def app(self) -> "ASGIApp":
        if self._app is None:
            current_path = self.request_data.path
            for route, app in self.server.apps.items():
                if route == "/":
                    if current_path == route:
                        self._app = app
                        return app
                elif current_path.startswith(route):
                    self.request_data.path = current_path.replace(route, "")
                    self._app = app
                    return app
            app = self.server.apps.get("/")  # type: ignore
            if app:
                self._app = app
                return app
            raise HTTPError(404)
        return self._app

    def handle_request(self) -> None:
        if not self.raw_request_data:
            self.close_socket()
            return None
        if (
            self.request_data.headers["connection"] == "Upgrade"
            and self.request_data.headers["upgrade"] == "websocket"
        ):
            self.loop.run_until_complete(self.websocket_loop())
            return None
        self.send_to_app(self.http_handler)

    def send_to_app(self, handler: Handler) -> None:
        self.loop.run_until_complete(
            self.app(handler.create_scope(), handler.receive, handler.send,)
        )

    def close_socket(self) -> None:
        self.closing = True
        try:
            self.send_to_app(self.http_handler)
        except HTTPError:
            pass
        self.get_proc_stats()
        super().close_socket()

    def get_proc_stats(self) -> None:
        if self.server.config.GATHER_PROC_STATS and psutil is not None:
            try:
                pid = multiprocessing.current_process().pid
                proc_stats = psutil.Process(pid=pid)
                stats = {}
                for key in self.server.config.PSUTIL_STAT_METHODS:
                    stats[key] = getattr(proc_stats, key)()
                self.stats_log.info(stats)

            except Exception as err:
                self.exception_log.exception(err, extra={"request_id": self.request_id})

    async def websocket_loop(self) -> None:
        self.websocket_handler.ws_shake_hand()
        await self.app(
            self.websocket_handler.create_scope(),
            self.websocket_handler.receive,
            self.websocket_handler.send,
        )
        if self.websocket_handler.state == WebSocketState.ACCEPTED:
            self.client_socket.sendall(self.response.to_http())
        else:
            raise HTTPError(403)
        self.response.clear()
        self.log_access()
        websocket = WebSocket()
        self.websocket_handler.websocket = websocket
        while True:
            websocket.clear_frames()
            await self.websocket_read(websocket)
            if websocket.should_terminate:
                self.close_socket()
                self.websocket_handler.state = WebSocketState.DISCONNECTED
                await self.app(
                    self.websocket_handler.create_scope(),
                    self.websocket_handler.receive,
                    self.websocket_handler.send,
                )
                break
            if websocket.being_pinged:
                await self.send_websocket_pong(websocket)
                continue

            # if websocket.read()

            await self.send_websocket_ping(websocket)

    async def send_websocket_ping(self, websocket: WebSocket) -> None:
        if randint(0, 20):
            websocket.clear_frames()
            websocket.write("ping", ping=True)
            response = websocket.pop_write_frame()
            if response:
                self.client_socket.sendall(response)
            frame = await self.get_websocket_frame()
            if not frame.is_pong and frame.message != "ping":
                raise WebSocketError(
                    "Client didn't respond properly after being pinged"
                )

    async def send_websocket_pong(self, websocket: WebSocket) -> None:
        message = websocket.read()
        websocket.write(message or "", pong=True)
        response = websocket.pop_write_frame()
        if response:
            self.client_socket.sendall(response)

    async def websocket_read(self, websocket: WebSocket) -> None:
        while not websocket.reading_complete:
            frame = await self.get_websocket_frame()
            websocket.add_read_frame(frame)

    async def get_websocket_frame(self) -> Frame:
        with BytesIO() as request_data:
            while True:
                try:
                    request_data.write(
                        self.client_socket.recv(self.server.config.RECV_BYTES)
                    )
                except socket.timeout:
                    pass
                frame = Frame(request_data.getvalue())
                if frame.is_complete:
                    break
            return frame


def make_child(server: "QactuarServer", client_socket: ssl.SSLSocket) -> None:
    child = ChildProcess(server, client_socket)
    child.start()
