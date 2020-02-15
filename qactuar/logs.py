from logging import INFO, Logger
from typing import Any, Dict, Optional


class QactuarLogger(Logger):
    def __init__(self, name: str, level: int = INFO):
        super().__init__(name, level)

    def exception(  # type: ignore
        self,
        msg: Any,
        *args: Any,
        exc_info=None,
        stack_info: bool = False,
        extra: Optional[Dict[str, Any]] = None,
        **kwargs: Any
    ) -> None:
        """
        The exception loggers formatter has the option of referencing a request_id. If
        the exception method is used in a context where there is no request_id this
        overriding method will set that field to a blank string so that the formatter
        doesn't blow up.
        """
        extra = extra or {"request_id": ""}
        if "request_id" not in extra:
            extra["request_id"] = ""
        super().exception(msg, *args, exc_info=exc_info, extra=extra, **kwargs)
