import multiprocessing
import socket
from typing import TYPE_CHECKING

from qactuar.exceptions import HTTPError
from qactuar.processes.base import BaseProcessHandler

try:
    import psutil  # type: ignore
except ImportError:
    psutil = None

if TYPE_CHECKING:
    from qactuar import QactuarServer, ASGIApp


class ChildProcess(BaseProcessHandler):
    def __init__(self, server: "QactuarServer", client_socket: socket.socket):
        super().__init__(server, client_socket)

    @property
    def app(self) -> "ASGIApp":
        current_path = self.request_data.path
        for route, app in self.server.apps.items():
            if route == "/":
                if current_path == route:
                    return app
            elif current_path.startswith(route):
                self.request_data.path = current_path.replace(route, "")
                return app
        app = self.server.apps.get("/")  # type: ignore
        if app:
            return app
        raise HTTPError(404)

    def handle_request(self) -> None:
        if not self.raw_request_data:
            self.close_socket()
            return None
        if (
            self.request_data.headers["Connection"] == "Upgrade"
            and self.request_data.headers["Upgrade"] == "websocket"
        ):
            self.server.websocket_handler.ws_shake_hand()
        self.loop.run_until_complete(
            self.app(
                self.server.http_handler.create_scope(),
                self.server.http_handler.receive,
                self.server.http_handler.send,
            )
        )

    def close_socket(self) -> None:
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
                self.child_log.info(stats)

            except Exception as err:
                self.exception_log.exception(err, extra={"request_id": self.request_id})


def make_child(server: "QactuarServer", client_socket: socket.socket) -> None:
    child = ChildProcess(server, client_socket)
    child.start()
