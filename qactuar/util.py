from dataclasses import dataclass
from typing import List, Union


class BytesList:
    def __init__(self) -> None:
        self._bytes_list: List[bytes] = []

    def write(self, new_bytes: bytes) -> None:
        self._bytes_list.append(new_bytes)

    def writelines(self, *bytes_list: Union[bytes, List[bytes]]) -> None:
        if len(bytes_list) == 1:
            if isinstance(bytes_list[0], (list, tuple)):
                bytes_list = bytes_list[0]  # type: ignore
        self._bytes_list.extend(bytes_list)  # type: ignore

    def read(self) -> bytes:
        return b"".join(self._bytes_list)

    def readlines(self) -> List[bytes]:
        return self._bytes_list

    def clear(self) -> None:
        self._bytes_list = []

    def __contains__(self, item: bytes) -> bool:
        return item in self.read()


@dataclass
class ProcStat:
    minor_faults: int = 0
    major_faults: int = 0
    user_time: int = 0
    system_time: int = 0
    virtual_size: int = 0
    resident_set_size: int = 0


@dataclass
class IoStat:
    read_char: int = 0
    write_char: int = 0
    read_bytes: int = 0
    write_bytes: int = 0


@dataclass
class MemStat:
    file_desc_size: int = 0
    vm_peak: int = 0
    vm_size: int = 0
    vm_highwm: int = 0
    vm_rss: int = 0
    vm_data: int = 0
    vm_lib: int = 0
    vm_pte: int = 0
    threads: int = 0


def parse_proc_stat_line(stat_line: str) -> ProcStat:
    parts = stat_line.split(" ")
    return ProcStat(
        minor_faults=int(parts[9]),
        major_faults=int(parts[11]),
        user_time=int(parts[13]),
        system_time=int(parts[14]),
        virtual_size=int(parts[22]),
        resident_set_size=int(parts[23]),
    )


io_stat_map = {
    "rchar": "read_char",
    "wchar": "write_char",
    "read_bytes": "read_bytes",
    "write_bytes": "write_bytes",
}


def parse_proc_io_line(io_line: str) -> IoStat:
    io_stat = IoStat()

    parts = io_line.split("\n")
    for part in parts:
        stat_parts = part.split(": ")
        if len(stat_parts) == 2:
            key, value = stat_parts
            if key in io_stat_map:
                setattr(io_stat, io_stat_map[key], int(value))

    return io_stat


mem_stat_map = {
    "FDSize": "file_desc_size",
    "VmPeak": "vm_peak",
    "VmSize": "vm_size",
    "VmHWM": "vm_highwm",
    "VmRSS": "vm_rss",
    "VmData": "vm_data",
    "VmLib": "vm_lib",
    "VmPTE": "vm_pte",
    "Threads": "threads",
}


def parse_proc_mem_line(mem_line: str) -> MemStat:
    mem_stat = MemStat()

    parts = mem_line.split("\n")
    for part in parts:
        stat_parts = part.split(":\t")
        if len(stat_parts) == 2:
            key, value = stat_parts
            if key in mem_stat_map:
                value = value.replace("kB", "")
                setattr(mem_stat, mem_stat_map[key], int(value))

    return mem_stat


try:
    import tornado
except ImportError:
    pass
else:
    from typing import Type

    from tornado.http1connection import HTTP1Connection
    from tornado.httputil import (
        HTTPServerRequest, HTTPHeaders, RequestStartLine,
    )
    from tornado.iostream import BaseIOStream
    from tornado.web import Application, RequestHandler

    from qactuar.logs import create_access_logger, create_child_logger


    class QactuarStream(BaseIOStream):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)

        def close_fd(self):
            pass

        def write_to_fd(self, data: memoryview) -> int:
            try:
                return len(data.tobytes())
            finally:
                del data

        def read_from_fd(self, buf):
            return len(buf)

        def fileno(self):
            return 0


    def to_bytes(value):
        return str(value).encode('utf-8')


    class TornadoWrapper:
        def __init__(self, tornado_handler: Type[RequestHandler]):
            self.logger = create_child_logger()
            self.access_logger = create_access_logger()
            self.scope = {}
            self.send = None
            self.receive = None
            self.handler_type = tornado_handler

        async def __call__(self, scope, receive, send):
            # noinspection PyAbstractClass
            class QactuarHandler(self.handler_type):
                def __init__(self, a, r, logger, **kwargs):
                    super().__init__(a, r, **kwargs)
                    self._qactuar_body = []
                    self._qactuar_headers = []
                    self._logger = logger

                def write(self, chunk):
                    super().write(chunk)
                    self._qactuar_body.append(to_bytes(chunk))

                def add_header(self, name, value):
                    super().add_header(name, value)
                    self._qactuar_headers.append((to_bytes(name), to_bytes(value)))

                def set_header(self, name, value):
                    super().set_header(name, value)
                    self._qactuar_headers.append((to_bytes(name), to_bytes(value)))

            if scope["type"] == 'http':
                self.scope = scope
                self.receive = receive
                self.send = send
                received = await receive()
                body = received['body']
                headers = HTTPHeaders({
                    header[0].decode('utf-8'): header[1].decode('utf-8')
                    for header in scope['headers']
                })
                request_start_line = RequestStartLine(
                    scope['method'],
                    scope['path'],
                    scope['http_version']
                )
                http_connection = HTTP1Connection(QactuarStream(), False)
                http_connection._request_start_line = request_start_line
                http_connection._request_headers = headers
                request = HTTPServerRequest(
                    method=scope['method'],
                    uri=scope['path'],
                    version=scope['http_version'],
                    headers=headers,
                    body=body,
                    host=scope['server'][0],
                    connection=http_connection,
                    start_line=request_start_line,
                )
                handler = QactuarHandler(Application(), request, self.logger, **{
                    'logging_level': 'DEBUG'
                })
                handler._transforms = []
                handler.application.transforms = []
                method_map = {
                    'GET': handler.get,
                    'POST': handler.post,
                    'PUT': handler.put,
                    'DELETE': handler.delete,
                    'OPTION': handler.options,
                    'HEAD': handler.head,
                    'PATCH': handler.patch,
                }
                try:
                    await method_map[scope['method']]()
                except Exception as err:
                    self.access_logger.exception(err)
                    result = b"500 Server Error"
                    handler.set_status(500)
                else:
                    result = b"".join(handler._qactuar_body)
                status = str(handler.get_status())
                response_headers = handler._qactuar_headers
                await send({
                    "type": "http.response.start",
                    "status": status,
                    "headers": response_headers
                })
                await send({
                    "type": "http.response.body",
                    "body": result,
                    "more_body": False
                })
