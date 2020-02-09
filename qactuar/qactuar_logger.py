from logging import INFO, Formatter, Logger, StreamHandler
from typing import Tuple


class QactuarLogger(Logger):
    def __init__(self, name: str, level: int):
        super().__init__(name, level)


class ChildHTTPLogger(QactuarLogger):
    def __init__(self, name: str, level: int):
        super().__init__(name, level)

    def access(
        self,
        client: Tuple[str, int],
        path: str,
        http_method: str,
        http_version: str,
        status: bytes,
        msg: str = "",
    ) -> None:
        self.info(
            f"{client[0]}:{client[1]} {http_method} HTTP/{http_version} "
            f"{status.decode('utf-8')} {path} {msg}"
        )


def create_http_access_logger() -> ChildHTTPLogger:
    logger = ChildHTTPLogger("qt_http_access", INFO)
    handler = StreamHandler()
    formatter = Formatter("{asctime} ACCESS {message}", style="{",)
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    return logger


def create_server_logger() -> QactuarLogger:
    logger = QactuarLogger("qt_server", INFO)
    handler = StreamHandler()
    formatter = Formatter("{asctime} {levelname} {message}", style="{")
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    return logger
