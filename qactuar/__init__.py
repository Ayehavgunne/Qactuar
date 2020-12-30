__version__ = "0.1.0"

from qactuar.config import Config, config_init
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
) -> BaseQactuarServer:
    if conf is None:
        conf = config_init()
    if conf.SERVER_TYPE.lower() == "simple_fork":
        return SimpleForkServer(host, port, app, conf)
    elif conf.SERVER_TYPE.lower() == "prefork":
        return PreForkServer(host, port, app, conf)
    elif conf.SERVER_TYPE.lower() == "async_only":
        return AsyncOnlyServer(host, port, app, conf)
    else:
        raise ValueError(f"server_type parameter not recognised: {conf.SERVER_TYPE}")


def run(
    host: str = None,
    port: int = None,
    app: ASGIApp = None,
    conf: Config = None,
) -> None:
    qactuar_server = make_server(host, port, app, conf)
    qactuar_server.serve_forever()
