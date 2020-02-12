import asyncio
import multiprocessing
import socket
import sys
from logging import getLogger
from pathlib import Path
from platform import system
from time import time
from typing import TYPE_CHECKING
from uuid import uuid4

from qactuar.exceptions import HTTPError
from qactuar.request import Request
from qactuar.response import Response
from qactuar.util import BytesList, parse_proc_io, parse_proc_mem, parse_proc_stat

if TYPE_CHECKING:
    from qactuar import QactuarServer, ASGIApp


class ChildProcess:
    def __init__(self, server: "QactuarServer", client_socket: socket.socket):
        self.loop = asyncio.new_event_loop()
        self.server = server
        self.child_log = getLogger("qt_child")
        self.access_log = getLogger("qt_access")
        self.exception_log = getLogger("qt_exception")
        self.client_socket = client_socket
        self.response: Response = Response()
        self.raw_request_data: bytes = b""
        self.request_data: Request = Request()
        self.request_id: str = str(uuid4())
        client_socket.settimeout(server.config.RECV_TIMEOUT)

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

    def handle_one_request(self) -> None:
        self.server.http_handler.set_child(self)
        try:
            self.get_request_data()
            if not self.raw_request_data:
                self.close_socket()
                return
            if (
                self.request_data.headers["Connection"]
                and self.request_data.headers["Upgrade"]
            ):
                self.server.websocket_handler.ws_shake_hand()
            self.loop.run_until_complete(
                self.app(
                    self.server.http_handler.create_scope(),
                    self.server.http_handler.receive,
                    self.server.http_handler.send,
                )
            )
        except KeyboardInterrupt:
            sys.exit(0)
        except HTTPError as err:
            self.response.status = str(err.args[0]).encode("utf-8")
            self.response.body.write(str(err.args[0]).encode("utf-8"))
        except Exception as err:
            self.exception_log.exception(err)
            self.response.status = b"500"
            self.response.body.write(b"Internal Server Error")
        finally:
            if self.response:
                self.access_log.info(
                    "",
                    extra={
                        "host": self.server.client_info[0],
                        "port": self.server.client_info[1],
                        "request_id": self.request_id,
                        "method": self.request_data.method,
                        "http_version": self.request_data.request_version_num,
                        "path": self.request_data.original_path or "/",
                        "status": self.response.status.decode("utf-8"),
                    },
                )
            self.finish_response()

    def get_request_data(self) -> None:
        request_data = BytesList()
        request = Request()
        start = time()

        while True:
            try:
                request_data.write(
                    self.client_socket.recv(self.server.config.RECV_BYTES)
                )
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

        self.request_data = request
        self.raw_request_data = request_data.read()

    # TODO: http.disconnect when socket closes
    def finish_response(self) -> None:
        try:
            if self.response:
                self.response.add_header("x-request-id", self.request_id)
                self.client_socket.sendall(self.response.to_http())
        except OSError as err:
            self.exception_log.exception(err)
        self.get_proc_stats()
        self.close_socket()
        sys.exit(0)

    def close_socket(self) -> None:
        try:
            self.client_socket.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        self.client_socket.close()

    def get_proc_stats(self) -> None:
        # see https://linux.die.net/man/5/proc
        if system() == "Linux" and self.server.config.GATHER_PROC_STATS:
            try:
                pid = multiprocessing.current_process().pid
                pid_path = Path("/proc") / str(pid)

                with (pid_path / "stat").open() as stat_file:
                    stats = stat_file.read()
                    sts = parse_proc_stat(stats)
                    self.child_log.info(sts)

                with (pid_path / "io").open() as io_file:
                    io = io_file.read()
                    ios = parse_proc_io(io)
                    self.child_log.info(ios)

                with (pid_path / "status").open() as status_file:
                    status = status_file.read()
                    stas = parse_proc_mem(status)
                    self.child_log.info(stas)

            except Exception as err:
                self.exception_log.exception(err)


def make_child(server: "QactuarServer", client_socket: socket.socket) -> None:
    child = ChildProcess(server, client_socket)
    child.handle_one_request()
