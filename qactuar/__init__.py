__version__ = "0.1.0"

from qactuar.config import Config
from qactuar.models import ASGIApp
from qactuar.servers.async_only import AsyncOnlyServer
from qactuar.servers.base import BaseQactuarServer
from qactuar.servers.prefork import PreForkServer
from qactuar.servers.simple_fork import SimpleForkServer


def make_server(
    host: str = None,
    port: int = None,
    app: ASGIApp = None,
    conf: Config = None,
    server_type: str = "async_only",
) -> BaseQactuarServer:
    if server_type.lower() == "simple_fork":
        return SimpleForkServer(host, port, app, conf)
    elif server_type.lower() == "prefork":
        return PreForkServer(host, port, app, conf)
    elif server_type.lower() == "async_only":
        return AsyncOnlyServer(host, port, app, conf)
    else:
        raise ValueError(f"server_type parameter not recognised: {server_type}")


def run(
    host: str = None,
    port: int = None,
    app: ASGIApp = None,
    conf: Config = None,
) -> None:
    qactuar_server = make_server(host, port, app, conf)
    qactuar_server.serve_forever()
