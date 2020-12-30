__version__ = "0.1.0"

from qactuar.config import Config
from qactuar.models import ASGIApp
from qactuar.servers.simple_fork import SimpleForkServer


def make_server(
    host: str = None,
    port: int = None,
    app: ASGIApp = None,
    conf: Config = None,
) -> SimpleForkServer:
    qactuar_server = SimpleForkServer(host, port, app, conf)
    return qactuar_server


def run(
    host: str = None,
    port: int = None,
    app: ASGIApp = None,
    conf: Config = None,
) -> None:
    qactuar_server = make_server(host, port, app, conf)
    qactuar_server.serve_forever()
