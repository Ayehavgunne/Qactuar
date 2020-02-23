import asyncio
import socket
import ssl
import sys
from io import BytesIO
from logging import getLogger
from time import time
from typing import TYPE_CHECKING
from uuid import uuid4

from qactuar.exceptions import HTTPError
from qactuar.request import Request
from qactuar.response import Response

try:
    import psutil  # type: ignore
except ImportError:
    psutil = None

if TYPE_CHECKING:
    from qactuar import QactuarServer


class BaseProcessHandler:
    def __init__(self, server: "QactuarServer", client_socket: ssl.SSLSocket):
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
        if self.server.ssl_context is None:
            client_socket.settimeout(server.config.RECV_TIMEOUT)

    def setup_ssl(self) -> None:
        if self.server.ssl_context:
            try:
                self.client_socket.do_handshake()
            except ssl.SSLError as err:
                if "sslv3 alert" not in err.args[1]:
                    self.exception_log.exception(err)
                    raise HTTPError(403)
            self.client_socket.settimeout(self.server.config.RECV_TIMEOUT)

    def start(self) -> None:
        try:
            if self.server.ssl_context is not None:
                self.setup_ssl()
            self.get_request_data()
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
                self.log_access()
            self.finish_response()

    def log_access(self) -> None:
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

    def get_request_data(self) -> None:
        with BytesIO() as request_data:
            request = Request()
            start = time()

            while True:
                try:
                    request_data.write(
                        self.client_socket.recv(self.server.config.RECV_BYTES)
                    )
                except socket.timeout:
                    pass
                if not request_data.getvalue():
                    if time() - start > self.server.config.REQUEST_TIMEOUT:
                        self.child_log.debug(
                            "no data received from request, timing out"
                        )
                        break
                request.raw_request = request_data.getvalue()
                if request.headers_complete:
                    content_length = request.headers["content-length"]
                    if content_length is not None and request.method != "GET":
                        if len(request.body) == int(content_length):
                            break
                        else:
                            continue
                    break

            self.request_data = request
            self.raw_request_data = request_data.getvalue()

    def finish_response(self) -> None:
        try:
            if self.response:
                self.response.add_header("x-request-id", self.request_id)
                self.client_socket.sendall(self.response.to_http())
        except OSError as err:
            self.exception_log.exception(err, extra={"request_id": self.request_id})
        self.response.body.close()
        self.close_socket()
        sys.exit(0)

    def close_socket(self) -> None:
        try:
            self.client_socket.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        self.client_socket.close()

    def handle_request(self) -> None:
        raise NotImplementedError
