import asyncio
import errno
import logging
import multiprocessing
import os
import select
import socket
import sys
from importlib import import_module
from logging import Logger
from time import time
from typing import Dict, Optional

from qactuar.config import Config, config_init
from qactuar.exceptions import HTTPError
from qactuar.models import ASGIApp, Message, Receive, Scope, Send
from qactuar.request import Request
from qactuar.response import Response
from qactuar.util import BytesList

ASGI_VERSION = {"version": "2.0", "spec_version": "2.0"}
LIFESPAN_SCOPE = {"type": "lifespan", "asgi": ASGI_VERSION}


class QactuarServer(object):
    address_family = socket.AF_INET
    socket_type = socket.SOCK_STREAM
    socket_level = socket.SOL_SOCKET
    socket_opt_name = socket.SO_REUSEADDR
    request_queue_size = 65536

    def __init__(
        self,
        host: str = None,
        port: int = None,
        app: ASGIApp = None,
        config: Config = None,
    ):
        if os.name != "nt":
            multiprocessing.set_start_method("fork")
        self.config: Config = config or config_init()

        self.logger: Logger = logging.getLogger("Qactuar")
        self.logger.setLevel(getattr(logging, self.config.LOG_LEVEL))
        self.logger.addHandler(logging.StreamHandler())

        self.host: str = host or self.config.HOST
        self.port: int = port or self.config.PORT

        self.listen_socket: socket.socket = socket.socket(
            self.address_family, self.socket_type
        )
        self.listen_socket.setsockopt(self.socket_level, self.socket_opt_name, 1)
        self.listen_socket.bind((self.host, self.port))
        self.listen_socket.listen(self.request_queue_size)

        self.admin_socket: socket.socket = socket.socket(
            self.address_family, self.socket_type
        )
        self.admin_socket.setsockopt(self.socket_level, self.socket_opt_name, 1)
        self.admin_socket.bind((self.config.ADMIN_HOST, self.config.ADMIN_PORT))
        self.admin_socket.listen(self.request_queue_size)

        self.server_name: str = socket.getfqdn(self.host)
        self.server_port: int = self.port

        self.client_connection: Optional[socket.socket] = None
        self.scheme: str = "http"
        self.raw_request_data: bytes = b""
        self.request_data: Request = Request()
        self.response: Response = Response()
        self.loop: asyncio.AbstractEventLoop = asyncio.get_event_loop()
        self.processes: Dict[int, multiprocessing.Process] = {}
        self.shutting_down: bool = False
        self.time_last_cleaned_processes: float = time()
        self.apps: Dict[str, ASGIApp] = {"/": app} if app else {}
        for route, app_path in self.config.APPS.items():
            module_str, app_str = app_path.split(":")
            app_module = import_module(module_str)
            self.apps[route] = getattr(app_module, app_str)
        if self.apps:
            self.start_up()
            self.serve_forever()
        else:
            self.logger.error("No apps found")
            self.shut_down()

    @property
    def app(self) -> ASGIApp:
        current_path = self.request_data.path
        for route, app in self.apps.items():
            if route == "/":
                if current_path == route:
                    return app
            elif current_path.startswith(route):
                self.request_data.path = current_path.replace(route, "")
                return app
        app = self.apps.get("/")
        if app:
            return app
        raise HTTPError(404)

    def add_app(self, application: ASGIApp, route: str = "/") -> None:
        self.apps[route] = application

    def serve_forever(self) -> None:
        try:
            while True:
                ready_to_read, _, _ = select.select(
                    [self.listen_socket], [], [], self.config.SELECT_SLEEP_TIME
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
        except IOError as err:
            if err.args[0] != errno.EINTR:
                raise
        else:
            if len(self.processes) > self.config.MAX_PROCESSES:
                self.response.status = b"503"
                self.response.body.write(b"Too many requests")
                connection.settimeout(self.config.RECV_TIMEOUT)
                self.client_connection = connection
                self.finish_response()
                self.response.status = b"200"
                self.response.body.clear()
            elif connection:
                connection.settimeout(self.config.RECV_TIMEOUT)
                self.client_connection = connection
                self.fork()

    def fork(self) -> None:
        self.loop = asyncio.new_event_loop()
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
        if (
            current_time - self.time_last_cleaned_processes
            > self.config.CHECK_PROCESS_INTERVAL
        ):
            self.time_last_cleaned_processes = current_time
            for ident, process in list(self.processes.items()):
                if not process.is_alive():
                    process.close()
                    del self.processes[ident]

    def send_to_all_apps(self, scope: Scope, receive: Receive, send: Send) -> None:
        for app in self.apps.values():
            self.loop.run_until_complete(app(scope, receive, send))

    def start_up(self) -> None:
        self.send_to_all_apps(LIFESPAN_SCOPE, self.lifespan_receive, self.send)
        self.logger.info(
            f"Qactuar: Serving {self.scheme.upper()} on {self.host}:{self.port}"
        )

    def shut_down(self) -> None:
        self.shutting_down = True
        self.logger.info("Shutting Down")
        self.send_to_all_apps(LIFESPAN_SCOPE, self.lifespan_receive, self.send)
        sys.exit(0)

    # TODO: http.disconnect when socket closes

    def handle_one_request(self) -> None:
        try:
            self.get_request_data()
            if not self.raw_request_data:
                self.close_socket()
                return
            if (
                self.request_data.headers["Connection"]
                and self.request_data.headers["Upgrade"]
            ):
                self.ws_shake_hand()
            app = self.app
            self.loop.run_until_complete(
                app(self.create_http_scope(), self.receive, self.send)
            )
            self.finish_response()
        except KeyboardInterrupt:
            sys.exit(0)
        except HTTPError as err:
            self.response.status = str(err.args[0]).encode("utf-8")
            self.response.body.write(str(err.args[0]).encode("utf-8"))
            self.finish_response()
        except Exception as err:
            self.logger.exception(err)
            self.response.status = b"500"
            self.response.body.write(b"wat happen?!")
            self.finish_response()

    def get_request_data(self) -> None:
        request_data = BytesList()
        request = Request()

        while True:
            try:
                request_data.write(self.client_connection.recv(self.config.RECV_BYTES))
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
        self.raw_request_data = request_data.read()

    async def send(self, data: Message) -> None:
        if data["type"] == "http.response.start":
            self.response.status = str(data["status"]).encode("utf-8")
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

    async def receive(self) -> Message:
        # TODO: support streaming from client
        return {
            "type": "http.request",
            "body": self.request_data.body,
            "more_body": False,
        }

    async def lifespan_receive(self) -> Message:
        return {
            "type": "lifespan.startup"
            if not self.shutting_down
            else "lifespan.shutdown",
            "asgi": ASGI_VERSION,
        }

    def ws_shake_hand(self):
        pass

    def create_websocket(self):
        pass

    def create_http_scope(self) -> Scope:
        # TODO: Pseudo headers (present in HTTP/2 and HTTP/3) must be removed; if
        #  :authority is present its value must be added to the start of the iterable
        #  with host as the header name or replace any existing host header already
        #  present.
        return {
            "type": "http",
            "asgi": ASGI_VERSION,
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

    def finish_response(self) -> None:
        try:
            self.client_connection.sendall(self.response.to_http())
        except OSError as err:
            self.logger.exception(err)
        finally:
            self.close_socket()

    def close_socket(self) -> None:
        try:
            self.client_connection.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        self.client_connection.close()
