import urllib.parse
from typing import List, Tuple

from qactuar.header import Header


class HTTPRequest:
    def __init__(self, request: bytes):
        self._raw_request: bytes = request
        self._command: str = ""
        self._request_version: str = ""
        self._path: str = ""
        self._query_string: bytes = b""
        self._headers = []
        self._parsed_headers: Header = Header()
        self._body: bytes = b""
        if request:
            self.parse()

    def parse(self):
        request = self._raw_request.decode("utf-8")
        lines = request.split("\r\n")
        self._command, self._path, self._request_version = lines.pop(0).split(" ")
        path_parts = self._path.split("?")
        self._path = path_parts[0]
        if len(path_parts) > 1:
            query_string = path_parts[1]
        else:
            query_string = ""
        self._query_string = query_string.encode("utf-8")
        line_num = 0
        for line in lines:
            if not line:
                break
            line_num += 1
            key, value = line.split(": ", 1)
            self._headers.append((key.lower().encode("utf-8"), value.encode("utf-8")))
        self._parsed_headers = Header(self._headers)
        for line in lines[line_num:]:
            self._body += line.encode("utf-8")

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
    def command(self) -> str:
        return self._command

    @property
    def path(self) -> str:
        return urllib.parse.unquote(self._path)

    @property
    def raw_path(self) -> bytes:
        return self._path.encode("utf-8")

    @property
    def query_string(self) -> bytes:
        return self._query_string

    @property
    def body(self) -> bytes:
        return self._body
