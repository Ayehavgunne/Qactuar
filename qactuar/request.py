import urllib.parse
from typing import List, Tuple

from qactuar.header import Header
from qactuar.models import Headers
from qactuar.util import BytesList


class Request:
    def __init__(self, request: bytes = None):
        self._raw_request: bytes = request or b""
        self._method: str = ""
        self._request_version: str = ""
        self._path: str = ""
        self._original_path: str = ""
        self._raw_path: bytes = b""
        self._query_string: bytes = b""
        self._headers: Headers = []
        self._parsed_headers: Header = Header()
        self._body: bytes = b""
        self.headers_complete = False
        if request:
            self.parse()

    def parse(self) -> None:
        lines = self._raw_request.split(b"\r\n")

        method, path, request_version = lines.pop(0).split(b" ")
        self._method = method.decode("utf-8")
        self._request_version = request_version.decode("utf-8")

        path_parts = path.split(b"?")
        self._path = urllib.parse.unquote(path_parts[0].decode("utf-8"))
        self._original_path = self._path
        self._raw_path = path_parts[0]
        if len(path_parts) > 1:
            query_string = path_parts[1]
        else:
            query_string = b""
        self._query_string = query_string

        line_num = 0
        for line in lines:
            if not line:
                self.headers_complete = True
                break
            line_num += 1
            key, value = line.split(b": ", 1)
            self._headers.append((key.lower(), value))
        self._parsed_headers = Header(self._headers)

        body = BytesList()
        body.writelines(lines[line_num:])
        self._body = body.read()

    @property
    def headers(self) -> Header:
        return self._parsed_headers

    @property
    def raw_headers(self) -> List[Tuple[bytes, bytes]]:
        return self._headers

    @property
    def request_version(self) -> str:
        return self._request_version

    @property
    def request_version_num(self) -> str:
        return self._request_version.replace("HTTP/", "")

    @property
    def method(self) -> str:
        return self._method

    @property
    def path(self) -> str:
        return self._path

    @path.setter
    def path(self, path: str) -> None:
        self._path = urllib.parse.unquote(path)

    @property
    def original_path(self) -> str:
        return self._original_path

    @property
    def raw_path(self) -> bytes:
        return self._raw_path

    @property
    def query_string(self) -> bytes:
        return self._query_string

    @property
    def body(self) -> bytes:
        return self._body

    @property
    def raw_request(self) -> bytes:
        return self._raw_request

    @raw_request.setter
    def raw_request(self, request: bytes) -> None:
        self._raw_request = request
        try:
            self.parse()
        except ValueError:
            self._reset_values()

    def _reset_values(self) -> None:
        self._method = ""
        self._request_version = ""
        self._path = ""
        self._original_path = ""
        self._raw_path = b""
        self._query_string = b""
        self._headers = []
        self._parsed_headers = Header()
        self._body = b""
        self.headers_complete = False
