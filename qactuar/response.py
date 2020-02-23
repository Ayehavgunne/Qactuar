from dataclasses import dataclass, field
from datetime import datetime
from email.utils import formatdate
from io import BytesIO
from time import mktime
from typing import Union

from qactuar.__version__ import VERSION
from qactuar.models import BasicHeaders


@dataclass
class Response:
    status: bytes = b"200"
    headers: BasicHeaders = field(default_factory=list)
    body: BytesIO = field(default_factory=BytesIO)

    def to_http(self) -> bytes:
        headers = [
            (b"Date", formatdate(mktime(datetime.now().timetuple())).encode("utf-8")),
            (b"Server", b"Qactuar " + VERSION.encode("utf-8")),
        ] + self.headers
        with BytesIO() as response:
            response.writelines((b"HTTP/1.1 ", self.status, b"\r\n"))
            for header in headers:
                key, value = header
                response.writelines((key, b": ", value, b"\r\n"))
            response.write(b"\r\n")
            response.write(self.body.getvalue())
            return response.getvalue()

    def clear(self) -> None:
        self.status = b"200"
        self.headers = []
        self.body.flush()

    def __bool__(self) -> bool:
        return bool(self.headers) or bool(self.body.getvalue())

    def add_header(self, name: Union[str, bytes], value: Union[str, bytes]) -> None:
        if isinstance(name, str):
            header_name = name.encode("utf-8")
        else:
            header_name = name
        if isinstance(value, str):
            header_value = value.encode("utf-8")
        else:
            header_value = value
        self.headers.append((header_name, header_value))
