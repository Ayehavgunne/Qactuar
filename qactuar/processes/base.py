import asyncio
import socket
import ssl
import sys
from logging import getLogger
from time import time
from typing import TYPE_CHECKING, Optional

from qactuar.exceptions import HTTPError
from qactuar.request import Request
from qactuar.response import Response
from qactuar.util import BytesList

if TYPE_CHECKING:
    from qactuar import ASGIApp
    from qactuar.servers.base import BaseQactuarServer


class BaseProcessHandler:
    def __init__(self, server: "BaseQactuarServer"):
        self.loop = asyncio.new_event_loop()
        self.server = server
        self._app: Optional["ASGIApp"] = None
        self.child_log = getLogger("qt_child")
        self.access_log = getLogger("qt_access")
        self.exception_log = getLogger("qt_exception")

    def get_app(self, request: Request) -> "ASGIApp":
        if self._app is None:
            current_path = request.path
            for route, app in self.server.apps.items():
                if route == "/":
                    if current_path == route:
                        self._app = app
                        return app
                elif current_path.startswith(route):
                    request.path = current_path.replace(route, "")
                    self._app = app
                    return app
            try:
                app = self.server.apps["/"]
            except KeyError:
                raise HTTPError(404)
            else:
                self._app = app
        return self._app

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
        self.access_log.info(
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

    def get_request_data(self, client_socket: socket.socket) -> Request:
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

    def finish_response(self, client_socket: socket.socket, response: Response) -> None:
        try:
            if response:
                response.add_header("x-request-id", response.request.request_id)
                client_socket.sendall(response.to_http())
        except OSError as err:
            self.exception_log.exception(
                err, extra={"request_id": response.request.request_id}
            )
        self.close_socket(client_socket, response.request)
        sys.exit(0)

    def close_socket(self, client_socket: socket.socket, request: Request) -> None:
        try:
            client_socket.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        client_socket.close()

    def start(self) -> None:
        raise NotImplementedError

    def handle_request(
        self, client_socket: socket.socket, request: Request
    ) -> Response:
        raise NotImplementedError

    def send_to_app(self, request: Request) -> Response:
        raise NotImplementedError
