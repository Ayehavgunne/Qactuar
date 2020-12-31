import asyncio
import errno
import multiprocessing
import os
import socket
import ssl
import sys
from importlib import import_module
from logging import Logger, getLogger, setLoggerClass
from logging.config import dictConfig
from typing import Dict, Optional, Tuple

from qactuar.config import Config, config_init
from qactuar.handlers import LifespanHandler
from qactuar.logs import QactuarLogger
from qactuar.models import ASGIApp, Receive, Scope, Send


class BaseQactuarServer(object):
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
            self.is_posix = True
        else:
            asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
            self.is_posix = False

        self.config: Config = config or config_init()

        setLoggerClass(QactuarLogger)
        dictConfig(self.config.LOGS)

        self.server_log: Logger = getLogger("qt_server")
        self.exception_log: Logger = getLogger("qt_exception")

        self.host: str = host or self.config.HOST
        self.port: int = port or self.config.PORT
        self.scheme: str = "http"

        self.listen_socket: socket.socket = socket.socket(
            self.address_family, self.socket_type
        )
        self.listen_socket.setsockopt(self.socket_level, self.socket_opt_name, 1)
        self.listen_socket.bind((self.host, self.port))
        self.listen_socket.listen(self.request_queue_size)

        self.ssl_context: Optional[ssl.SSLContext] = None
        if self.config.SSL_CERT_PATH and self.config.SSL_KEY_PATH:
            self.setup_ssl()

        self.server_name: str = socket.getfqdn(self.host)
        self.server_port: int = self.port

        self.client_info: Tuple[str, int] = ("", 0)
        self.loop = asyncio.get_event_loop()
        self.processes: Dict[int, multiprocessing.Process] = {}
        self.shutting_down: bool = False
        self.lifespan_handler: LifespanHandler = LifespanHandler(self)
        self.apps: Dict[str, ASGIApp] = {"/": app} if app else {}
        for route, app_path in self.config.APPS.items():
            module_str, app_str = app_path.split(":")
            app_module = import_module(module_str)
            self.apps[route] = getattr(app_module, app_str)

    def serve_forever(self) -> None:
        raise NotImplementedError

    def add_app(self, application: ASGIApp, route: str = "/") -> None:
        self.apps[route] = application

    def start_up(self) -> None:
        self.send_to_all_apps(
            self.lifespan_handler.create_scope(),
            self.lifespan_handler.receive,
            self.lifespan_handler.send,
        )
        self.server_log.info(
            f"Qactuar: Serving {self.scheme.upper()} on {self.host}:{self.port}"
        )

    def shut_down(self) -> None:
        self.shutting_down = True
        self.server_log.info("Shutting Down")
        self.send_to_all_apps(
            self.lifespan_handler.create_scope(),
            self.lifespan_handler.receive,
            self.lifespan_handler.send,
        )
        sys.exit(0)

    async def async_shut_down(self) -> None:
        self.shutting_down = True
        self.server_log.info("Shutting Down")
        await self.async_send_to_all_apps(
            self.lifespan_handler.create_scope(),
            self.lifespan_handler.receive,
            self.lifespan_handler.send,
        )
        sys.exit(0)

    def setup_ssl(self) -> None:
        context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
        context.load_cert_chain(self.config.SSL_CERT_PATH, self.config.SSL_KEY_PATH)
        context.options |= ssl.PROTOCOL_TLS
        context.set_ciphers(self.config.SSL_CIPHERS)
        self.ssl_context = context
        self.scheme = "https"
        self.listen_socket = context.wrap_socket(
            self.listen_socket, server_side=True, do_handshake_on_connect=False
        )

    def send_to_all_apps(self, scope: Scope, receive: Receive, send: Send) -> None:
        for app in self.apps.values():
            self.loop.run_until_complete(app(scope, receive, send))

    async def async_send_to_all_apps(
        self, scope: Scope, receive: Receive, send: Send
    ) -> None:
        for app in self.apps.values():
            await app(scope, receive, send)

    def accept_client_connection(self) -> Optional[socket.socket]:
        try:
            client_socket, self.client_info = self.listen_socket.accept()
        except IOError as err:
            if err.args[0] != errno.EINTR:
                raise
            return None
        else:
            return client_socket

    async def async_accept_client_connection(self) -> Optional[socket.socket]:
        try:
            client_socket, self.client_info = await self.loop.sock_accept(
                self.listen_socket
            )
        except IOError as err:
            if err.args[0] != errno.EINTR:
                raise
            return None
        else:
            return client_socket
