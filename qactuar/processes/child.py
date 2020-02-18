import multiprocessing
import socket
from logging import getLogger
from random import randint
from time import sleep
from typing import TYPE_CHECKING, Optional

from qactuar.exceptions import HTTPError
from qactuar.processes.base import BaseProcessHandler
from qactuar.util import BytesList
from qactuar.websocket import Frame, WebSocket

try:
    import psutil  # type: ignore
except ImportError:
    psutil = None

if TYPE_CHECKING:
    from qactuar import QactuarServer, ASGIApp


class ChildProcess(BaseProcessHandler):
    def __init__(self, server: "QactuarServer", client_socket: socket.socket):
        super().__init__(server, client_socket)
        del self.server.admin_queue
        self.server.http_handler.set_child(self)
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
            self.server.websocket_handler.set_child(self)
            self.server.websocket_handler.ws_shake_hand()
            self.client_socket.sendall(self.response.to_http())
            self.log_access()
            self.start_websocket()
            self.response.clear()
            return None
        self.send_to_app()

    def send_to_app(self) -> None:
        self.loop.run_until_complete(
            self.app(
                self.server.http_handler.create_scope(),
                self.server.http_handler.receive,
                self.server.http_handler.send,
            )
        )

    def close_socket(self) -> None:
        self.closing = True
        try:
            self.send_to_app()
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

    def start_websocket(self) -> None:
        websocket = WebSocket()
        frame = self.get_websocket_frame()
        websocket.add_read_frame(frame)
        while True:
            self.websocket_read(websocket)
            if websocket.should_terminate:
                self.close_socket()
                break
            if websocket.being_pinged:
                message = websocket.read()
                websocket.write(message or "", pong=True)
                response = websocket.response
                if response:
                    self.client_socket.sendall(response)
            if randint(0, 1):
                websocket.clear_frames()
                websocket.write("ping", ping=True)
                response = websocket.response
                if response:
                    self.client_socket.sendall(response)
                frame = self.get_websocket_frame()
                if frame.is_pong and frame.message == "ping":
                    print("ponged")
                else:
                    print(frame.message)
            websocket.clear_frames()

    def websocket_read(self, websocket: WebSocket) -> None:
        while not websocket.reading_complete:
            frame = self.get_websocket_frame()
            websocket.add_read_frame(frame)
        message = websocket.read()
        if message:  # TODO: send message to app and send app responses back
            sleep(1)
            websocket.write(message)
            try:
                response = websocket.response
                if response:
                    self.client_socket.sendall(response)
            except OSError as err:
                self.exception_log.exception(err)

    def get_websocket_frame(self) -> Frame:
        request_data = BytesList()

        while True:
            try:
                request_data.write(
                    self.client_socket.recv(self.server.config.RECV_BYTES)
                )
            except socket.timeout:
                pass
            frame = Frame(request_data.read())
            if frame.is_complete:
                break
        return frame


def make_child(server: "QactuarServer", client_socket: socket.socket) -> None:
    child = ChildProcess(server, client_socket)
    child.start()
