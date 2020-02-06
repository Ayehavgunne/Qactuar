from qactuar.config import Config
from qactuar.models import ASGIApp
from qactuar.server import QactuarServer


def make_server(
    host: str = None, port: int = None, app: ASGIApp = None, conf: Config = None,
) -> QactuarServer:
    qactuar_server = QactuarServer(host, port, app, conf)
    return qactuar_server


def run(
    host: str = None, port: int = None, app: ASGIApp = None, conf: Config = None,
) -> None:
    qactuar_server = make_server(host, port, app, conf)
    qactuar_server.serve_forever()
