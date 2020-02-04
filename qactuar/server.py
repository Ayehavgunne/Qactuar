import asyncio
import errno
import logging
import multiprocessing
import select
import socket
import sys
from datetime import datetime
from email.utils import formatdate
from logging import Logger
from time import mktime, time
from typing import Callable, Dict, List, Optional, Tuple

from qactuar import __version__
from qactuar.request import Request
from qactuar.response import Response
from qactuar.util import BytesList

CHECK_PROCESS_INTERVAL = 1
SELECT_SLEEP_TIME = 0.025
MAX_CHILD_PROCESSES = 100
RECV_TIMEOUT = 0.01
RECV_BYTES = 65536


class QactuarServer(object):
    address_family = socket.AF_INET
    socket_type = socket.SOCK_STREAM
    request_queue_size = 1024

    def __init__(self, server_address: Tuple[str, int]):
        self.host, self.port = server_address
        self.listen_socket = listen_socket = socket.socket(
            self.address_family, self.socket_type
        )

        listen_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        listen_socket.bind(server_address)
        listen_socket.listen(self.request_queue_size)

        self.server_name: str = socket.getfqdn(self.host)
        self.server_port: int = self.port

        self.logger: Logger = logging.getLogger()
        self.logger.setLevel(logging.INFO)
        self.logger.addHandler(logging.StreamHandler())

        self.application: Optional[Callable] = None
        self.client_connection: Optional[socket.socket] = None
        self.scheme: str = "http"
        self.raw_request_data: bytes = b""
        self.request_data: Request = Request()
        self.response: Response = Response()
        self.loop: asyncio.AbstractEventLoop = asyncio.get_event_loop()
        self.processes: Dict[int, multiprocessing.Process] = {}
        self.shutting_down: bool = False
        self.time_last_cleaned_processes: float = time()

    def set_app(self, application) -> None:
        self.application = application
        self.start_up()

    def serve_forever(self) -> None:
        try:
            while True:
                ready_to_read, _, _ = select.select(
                    [self.listen_socket], [], [], SELECT_SLEEP_TIME
                )
                if ready_to_read:
                    self.check_socket()
                self.check_processes()
        except KeyboardInterrupt:
            self.shut_down()
        except Exception as err:
            self.logger.exception(err)

    def check_socket(self) -> None:
        try:
            connection, _ = self.listen_socket.accept()
        except IOError as e:
            code, msg = e.args
            if code != errno.EINTR:
                raise
        else:
            if connection:
                self.client_connection = connection
                self.client_connection.settimeout(RECV_TIMEOUT)
                self.fork()

    def fork(self) -> None:
        process = multiprocessing.Process(target=self.handle_one_request)
        process.daemon = True
        try:
            process.start()
        except AttributeError:
            self.logger.warning(f"Could not start process {process.ident}")
        else:
            self.processes[process.ident] = process

    def check_processes(self) -> None:
        current_time = time()
        if current_time - self.time_last_cleaned_processes > CHECK_PROCESS_INTERVAL:
            self.time_last_cleaned_processes = current_time
            for ident, process in list(self.processes.items()):
                if not process.is_alive():
                    process.close()
                    del self.processes[ident]

    def start_up(self) -> None:
        self.loop.run_until_complete(
            self.application(
                self.create_lifespan_scope(), self.lifespan_receive, self.send
            )
        )
        self.logger.info(
            f"Qactuar: Serving {self.scheme.upper()} on {self.host}:{self.port}"
        )

    def shut_down(self) -> None:
        self.shutting_down = True
        self.logger.info("Shutting Down")
        self.loop.run_until_complete(
            self.application(
                self.create_lifespan_scope(), self.lifespan_receive, self.send
            )
        )
        sys.exit(0)

    # TODO: http.disconnect when socket closes

    def handle_one_request(self) -> None:
        self.raw_request_data = self.get_request_data()
        if not self.raw_request_data:
            self.close_socket()
            return
        self.client_connection.settimeout(None)
        if (
            self.request_data.headers["Connection"]
            and self.request_data.headers["Upgrade"]
        ):
            self.ws_shake_hand()
        self.loop.run_until_complete(
            self.application(self.create_http_scope(), self.receive, self.send)
        )
        self.finish_response()

    def get_request_data(self) -> bytes:
        request_data = BytesList()
        request = Request()

        while True:
            try:
                request_data.write(self.client_connection.recv(RECV_BYTES))
            except socket.timeout:
                request.raw_request = request_data.read()
                if request.headers_complete:
                    content_length = request.headers["content-length"]
                    if content_length is not None and request.command != "GET":
                        if len(request.body) == int(content_length):
                            break
                        else:
                            continue
                    break

        self.request_data = request
        return request_data.read()

    async def send(self, data: Dict) -> None:
        if data["type"] == "http.response.start":
            self.response.status = data["status"]
            self.response.headers = data["headers"]
        if data["type"] == "http.response.body":
            # TODO: check "more_body" and if true then do self.client_connection.send()
            #  the current data
            self.response.body.write(data["body"])
        if (
            data["type"] == "lifespan.startup.failed"
            or data["type"] == "lifespan.shutdown.failed"
        ):
            if "startup" in data["type"]:
                self.logger.error("App startup failed")
            if "shutdown" in data["type"]:
                self.logger.error("App shutdown failed")
            self.logger.error(data["message"])

    async def receive(self) -> Dict:
        # TODO: support streaming from client
        return {
            "type": "http.request",
            "body": self.request_data.body,
            "more_body": False,
        }

    async def lifespan_receive(self) -> Dict:
        return {
            "type": "lifespan.startup"
            if not self.shutting_down
            else "lifespan.shutdown",
            "asgi": {"version": "2.0", "spec_version": "2.0"},
        }

    def ws_shake_hand(self):
        pass

    def create_websocket(self):
        pass

    @staticmethod
    def create_lifespan_scope() -> Dict:
        return {"type": "lifespan", "asgi": {"version": "2.0", "spec_version": "2.0"}}

    def create_http_scope(self) -> Dict:
        # TODO: Pseudo headers (present in HTTP/2 and HTTP/3) must be removed; if
        #  :authority is present its value must be added to the start of the iterable
        #  with host as the header name or replace any existing host header already
        #  present.
        return {
            "type": "http",
            "asgi": {"version": "2.0", "spec_version": "2.0"},
            "http_version": self.request_data.request_version_num,
            "method": self.request_data.command,
            "scheme": self.scheme,
            "path": self.request_data.path,
            "raw_path": self.request_data.raw_path,
            "query_string": self.request_data.query_string,
            "root_path": "",
            "headers": self.request_data.raw_headers,
            "client": self.client_connection.getpeername(),
            "server": (self.server_name, self.server_port),
        }

    def compile_headers(self) -> List[Tuple[bytes, bytes]]:
        server_headers = [
            (b"Date", formatdate(mktime(datetime.now().timetuple())).encode("utf-8")),
            (b"Server", b"Qactuar " + __version__.encode("utf-8")),
        ]
        return self.response.headers + server_headers

    def finish_response(self) -> None:
        try:
            response_headers = self.compile_headers()
            response = BytesList()
            response.write(b"HTTP/1.1 ")
            response.write(str(self.response.status).encode("utf-8"))
            response.write(b"\r\n")
            for header in response_headers:
                key, value = header
                response.write(key)
                response.write(b": ")
                response.write(value)
                response.write(b"\r\n")
            response.write(b"\r\n")
            response.write(self.response.body.read())
            self.client_connection.sendall(response.read())
        finally:
            self.close_socket()

    def close_socket(self) -> None:
        try:
            self.client_connection.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        self.client_connection.close()
