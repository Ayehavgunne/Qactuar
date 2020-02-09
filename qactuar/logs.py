from logging import INFO, Logger


class QactuarLogger(Logger):
    def __init__(self, name: str, level: int = INFO):
        super().__init__(name, level)
