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

from qactuar.child_process import make_child
from qactuar.config import Config, config_init
from qactuar.exceptions import HTTPError
from qactuar.handlers import HTTPHandler, LifespanHandler, WebSocketHandler
from qactuar.models import ASGIApp, Receive, Scope, Send
from qactuar.request import Request
from qactuar.response import Response


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
            self.is_posix = False
        else:
            self.is_posix = True

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
        self.client_info = ("", 0)
        self.scheme: str = "http"
        self.raw_request_data: bytes = b""
        self.request_data: Request = Request()
        self.response: Response = Response()
        self.loop: asyncio.AbstractEventLoop = asyncio.get_event_loop()
        self.processes: Dict[int, multiprocessing.Process] = {}
        self.shutting_down: bool = False
        self.time_last_cleaned_processes: float = time()
        self.lifespan_handler: LifespanHandler = LifespanHandler(self)
        self.http_handler: HTTPHandler = HTTPHandler(self)
        self.websocket_handler: WebSocketHandler = WebSocketHandler(self)
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
        app = self.apps.get("/")  # type: ignore
        if app:
            return app
        raise HTTPError(404)

    def add_app(self, application: ASGIApp, route: str = "/") -> None:
        self.apps[route] = application

    def start_up(self) -> None:
        self.send_to_all_apps(
            self.lifespan_handler.create_scope(),
            self.lifespan_handler.receive,
            self.lifespan_handler.send,
        )
        self.logger.info(
            f"Qactuar: Serving {self.scheme.upper()} on {self.host}:{self.port}"
        )

    def shut_down(self) -> None:
        self.shutting_down = True
        self.logger.info("Shutting Down")
        self.send_to_all_apps(
            self.lifespan_handler.create_scope(),
            self.lifespan_handler.receive,
            self.lifespan_handler.send,
        )
        sys.exit(0)

    def send_to_all_apps(self, scope: Scope, receive: Receive, send: Send) -> None:
        for app in self.apps.values():
            self.loop.run_until_complete(app(scope, receive, send))

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
            connection.settimeout(self.config.RECV_TIMEOUT)
            self.client_connection = connection
        except IOError as err:
            if err.args[0] != errno.EINTR:
                raise
        else:
            self.client_info = self.client_connection.getpeername()
            if len(self.processes) > self.config.MAX_PROCESSES:
                self.response.status = b"503"
                self.response.body.write(b"Service Unavailable")
                self.finish_response()
                self.response.status = b"200"
                self.response.body.clear()
            elif connection:
                self.fork()

    def fork(self) -> None:
        process = multiprocessing.Process(target=make_child, args=(self,))
        process.daemon = True
        try:
            process.start()
        except AttributeError as err:
            self.logger.exception(err)
            self.logger.warning(f"Could not start process {process.ident}")
        else:
            ident = process.ident
            if ident:
                self.processes[ident] = process

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

    # TODO: http.disconnect when socket closes
    def finish_response(self) -> None:
        try:
            if self.client_connection:
                self.client_connection.sendall(self.response.to_http())
        except OSError as err:
            self.logger.exception(err)
        finally:
            self.close_socket()

    def close_socket(self) -> None:
        if self.client_connection:
            try:
                self.client_connection.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            self.client_connection.close()
