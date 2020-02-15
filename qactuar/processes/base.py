import asyncio
import socket
import sys
from logging import getLogger
from time import time
from typing import TYPE_CHECKING
from uuid import uuid4

from qactuar.exceptions import HTTPError
from qactuar.request import Request
from qactuar.response import Response
from qactuar.util import BytesList

try:
    import psutil  # type: ignore
except ImportError:
    psutil = None

if TYPE_CHECKING:
    from qactuar import QactuarServer


class BaseProcessHandler:
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

    def start(self) -> None:
        self.server.http_handler.set_child(self)
        self.get_request_data()
        try:
            self.handle_request()
        except KeyboardInterrupt:
            sys.exit(0)
        except HTTPError as err:
            self.response.status = str(err.args[0]).encode("utf-8")
            self.response.body.write(str(err.args[0]).encode("utf-8"))
        except Exception as err:
            self.exception_log.exception(err, extra={"request_id": self.request_id})
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
            self.exception_log.exception(err, extra={"request_id": self.request_id})
        self.close_socket()
        sys.exit(0)

    def close_socket(self) -> None:
        try:
            self.client_socket.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        self.client_socket.close()

    def handle_request(self) -> None:
        pass
