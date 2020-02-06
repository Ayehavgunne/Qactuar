import json
import os
from dataclasses import dataclass, field
from logging import getLogger
from pathlib import Path
from typing import Dict


@dataclass
class Config:
    HOST: str = "localhost"
    PORT: int = 8000
    LOG_LEVEL: str = "DEBUG"
    CHECK_PROCESS_INTERVAL: int = 1
    SELECT_SLEEP_TIME: float = 0.025
    RECV_TIMEOUT: float = 0.001
    RECV_BYTES: int = 65536
    MAX_PROCESSES: int = 500
    APPS: Dict[str, str] = field(default_factory=dict)


def config_init() -> Config:
    logger = getLogger("Qactuar")
    path_str = os.environ.get("QACTUAR_CONFIG_DIR")
    config_path = Path(path_str or "")
    if not config_path.is_file():
        logger.warning(
            f"Config file path is not valid or not set, loading default values. To use "
            f"a config file set up an environment variable called 'QACTUAR_CONFIG_DIR' "
            f"and set the value to a JSON config file path."
        )
        return Config()
    return Config(**json.loads(config_path.open().read()))
