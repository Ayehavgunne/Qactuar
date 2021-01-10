import asyncio
import errno
import multiprocessing
import os
import select
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
from qactuar.models import ASGIApp


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

    def run(self) -> None:
        self.start_up()
        try:
            self.loop.run_until_complete(self.serve_forever())
        except KeyboardInterrupt:
            self.shut_down()
        except Exception as err:
            self.exception_log.exception(err)
            self.shut_down()

    async def serve_forever(self) -> None:
        raise NotImplementedError

    def add_app(self, app: ASGIApp, route: str = "/") -> None:
        self.apps[route] = app

    def start_up(self) -> None:
        self.lifespan_handler.start()
        self.server_log.info(
            f"Qactuar: Serving {self.scheme.upper()} on {self.host}:{self.port}"
        )

    def shut_down(self) -> None:
        self.server_log.info("Shutting Down")
        self.shutting_down = True
        self.lifespan_handler.shutdown()
        pending = asyncio.all_tasks(self.loop)
        self.loop.run_until_complete(asyncio.gather(*pending))
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

    async def accept_client_connection(self) -> Optional[socket.socket]:
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

    def watch_socket(self) -> bool:
        try:
            ready_to_read, _, _ = select.select(
                [self.listen_socket], [], [], self.config.SELECT_SLEEP_TIME
            )
            return len(ready_to_read) > 0
        except KeyboardInterrupt:
            return False
