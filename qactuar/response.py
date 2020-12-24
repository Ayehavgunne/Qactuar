from dataclasses import dataclass, field
from datetime import datetime
from email.utils import formatdate
from time import mktime
from typing import Union

from qactuar import __version__
from qactuar.models import Headers
from qactuar.util import BytesList


@dataclass
class Response:
    status: bytes = b"200"
    headers: Headers = field(default_factory=list)
    body: BytesList = field(default_factory=BytesList)

    def to_http(self) -> bytes:
        headers = [
            (b"Date", formatdate(mktime(datetime.now().timetuple())).encode("utf-8")),
            (b"Server", b"Qactuar " + __version__.encode("utf-8")),
        ] + self.headers
        response = BytesList()
        response.writelines(b"HTTP/1.1 ", self.status, b"\r\n")
        for header in headers:
            key, value = header
            response.writelines(key, b": ", value, b"\r\n")
        response.write(b"\r\n")
        response.writelines(self.body.readlines())
        return response.read()

    def clear(self) -> None:
        self.status = b"200"
        self.headers = []
        self.body.clear()

    def __bool__(self) -> bool:
        return bool(self.headers) or bool(self.body)

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
