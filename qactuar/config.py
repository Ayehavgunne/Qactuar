import json
import os
from dataclasses import dataclass, field
from logging import getLogger
from pathlib import Path
from typing import Any, Dict, List


def default_log_config() -> Dict[str, Any]:
    return {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "standard": {"format": "{asctime} {levelname} {message}", "style": "{"},
            "access": {
                "format": "{asctime} ACCESS {host}:{port} {request_id} {method} "
                "HTTP/{http_version} {path} {status} {message}",
                "style": "{",
            },
            "exception": {
                "format": "{asctime} {levelname} {request_id} {message}",
                "style": "{",
            },
            "stats": {"format": "{message}", "style": "{"},
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "level": "INFO",
                "formatter": "standard",
                "stream": "ext://sys.stdout",
            },
            "access": {
                "class": "logging.StreamHandler",
                "level": "INFO",
                "formatter": "access",
                "stream": "ext://sys.stdout",
            },
            "exception": {
                "class": "logging.StreamHandler",
                "level": "ERROR",
                "formatter": "exception",
                "stream": "ext://sys.stderr",
            },
            "stats": {
                "class": "logging.StreamHandler",
                "level": "INFO",
                "formatter": "stats",
                "stream": "ext://sys.stdout",
            },
        },
        "loggers": {
            "qt_server": {"handlers": ["console"], "level": "DEBUG"},
            "qt_child": {"handlers": ["console"], "level": "DEBUG"},
            "qt_access": {"handlers": ["access"], "level": "INFO"},
            "qt_exception": {"handlers": ["exception"], "level": "ERROR"},
            "qt_stats": {"handlers": ["stats"], "level": "INFO"},
        },
    }


def default_psutil_methods() -> List[str]:
    return ["cpu_times", "io_counters", "memory_info"]


@dataclass
class Config:
    HOST: str = "localhost"
    PORT: int = 8000
    ADMIN_HOST: str = "localhost"
    ADMIN_PORT: int = 1986
    CHECK_PROCESS_INTERVAL: int = 1
    SELECT_SLEEP_TIME: float = 0.00001
    RECV_TIMEOUT: float = 0.01
    RECV_BYTES: int = 65536
    MAX_PROCESSES: int = 5000
    REQUEST_TIMEOUT: float = 0.5
    GATHER_PROC_STATS: bool = False
    # see https://psutil.readthedocs.io/en/latest/#process-class for available methods
    PSUTIL_STAT_METHODS: List[str] = field(default_factory=default_psutil_methods)
    SSL_CERT_PATH: str = ""
    SSL_KEY_PATH: str = ""
    SSL_CIPHERS: str = "EECDH+AESGCM:EDH+AESGCM:AES256+EECDH:AES256+EDH"

    APPS: Dict[str, str] = field(default_factory=dict)
    LOGS: Dict[str, Any] = field(default_factory=default_log_config)


def config_init() -> Config:
    logger = getLogger("Qactuar")
    env_var_name = "QACTUAR_CONFIG"
    path_str = os.environ.get(env_var_name)
    config_path = Path(path_str or "")
    if not config_path.is_file():
        logger.warning(
            f"Config file path is not valid or not set, loading default values. To use "
            f"a config file set up an environment variable called '{env_var_name}' and "
            f"set the value to a JSON config file path."
        )
        return Config()
    return Config(**json.loads(config_path.open().read()))
