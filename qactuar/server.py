import asyncio
import errno
import multiprocessing
import select
import socket
import sys
import urllib.parse
from datetime import datetime
from email.utils import formatdate
from time import mktime, time
from typing import Dict, Optional, Tuple

from qactuar.request import HTTPRequest

CHECK_PROCESS_INTERVAL = 1
SELECT_SLEEP_TIME = 0
MAX_CHILD_PROCESSES = 100
RECV_TIMEOUT = 0.1


class QactuarServer(object):
    address_family = socket.AF_INET
    socket_type = socket.SOCK_STREAM
    request_queue_size = 1024

    def __init__(self, server_address: Tuple[str, int]):
        host, port = server_address
        print(f"Qactuar: Serving HTTP on {host}:{port} ...")
        self.listen_socket = listen_socket = socket.socket(
            self.address_family, self.socket_type
        )
        listen_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        listen_socket.bind(server_address)
        listen_socket.listen(self.request_queue_size)
        self.server_name = socket.getfqdn(host)
        self.server_port = port
        self.application = None
        self.client_connection: Optional[socket.socket] = None
        self.scheme = "http"
        self.raw_request_data = None
        self.request_data: Optional[HTTPRequest] = None
        self.response = {
            "status": b"200 OK",
            "headers": [],
            "body": b"",
        }
        self.processes: Dict[int, multiprocessing.Process] = {}
        self.shutting_down = False
        self.time_last_cleaned_processes = time()

    def set_app(self, application):
        self.application = application

    def serve_forever(self):
        while True:
            ready_to_read, _, _ = select.select(
                [self.listen_socket], [], [], SELECT_SLEEP_TIME
            )
            if ready_to_read:
                self.check_socket()
            self.check_processes()

    def check_socket(self):
        try:
            connection, _ = self.listen_socket.accept()
        except IOError as e:
            code, msg = e.args
            if code != errno.EINTR:
                raise
        except KeyboardInterrupt:
            self.shut_down()
        else:
            if connection:
                self.client_connection = connection
                self.client_connection.settimeout(RECV_TIMEOUT)
                self.fork()

    def fork(self):
        process = multiprocessing.Process(target=self.handle_one_request)
        process.daemon = True
        try:
            process.start()
        except AttributeError:
            print(f"Could not start process {process.ident}")
        else:
            self.processes[process.ident] = process

    def check_processes(self):
        if time() - self.time_last_cleaned_processes > CHECK_PROCESS_INTERVAL:
            self.time_last_cleaned_processes = time()
            for ident, process in list(self.processes.items()):
                if not process.is_alive():
                    process.close()
                    del self.processes[ident]

    def shut_down(self):
        self.shutting_down = True
        print("shutting down")
        sys.exit(0)

    def handle_one_request(self):
        self.raw_request_data = self.get_request_data()
        if not self.raw_request_data:
            self.close_socket()
            return
        self.client_connection.settimeout(None)
        self.request_data = HTTPRequest(self.raw_request_data)
        env = self.create_scope()
        loop = asyncio.get_event_loop()
        loop.run_until_complete(self.application(env, self.recieve, self.send))
        self.finish_response()

    def get_request_data(self) -> bytes:
        request_data = b""
        new_data = b""
        while True:
            request_data += new_data
            try:
                new_data = self.client_connection.recv(1024)
            except socket.timeout:
                break
        return request_data

    async def send(self, data: Dict, _=None):
        if data["type"] == "http.response.start":
            self.response["status"] = data["status"]
            self.response["headers"] = data["headers"]
        if data["type"] == "http.response.body":
            # TODO: check "more_body" and if true then do self.client_connection.send()
            #  the current data
            self.response["body"] += data["body"]

    async def recieve(self, _=None):
        body = self.raw_request_data.split(b"\r\n\r\n")
        if len(body) > 1:
            body = body[1]
        else:
            body = b""
        # TODO: support streaming from client
        return {
            "type": "http.request",
            "body": body,
            "more_body": False,
        }

    def create_scope(self):
        # TODO: Pseudo headers (present in HTTP/2 and HTTP/3) must be removed; if
        #  :authority is present its value must be added to the start of the iterable
        #  with host as the header name or replace any existing host header already
        #  present.
        return {
            "type": "http",
            "asgi": {"version": "2.0", "spec_version": "2.0"},
            "http_version": self.request_data.request_version.replace("HTTP/", ""),
            "method": self.request_data.command,
            "scheme": self.scheme,
            "path": urllib.parse.unquote(self.get_path()),
            "raw_path": self.get_path().encode("utf-8"),
            "query_string": self.get_query_string(),
            "root_path": "",
            "headers": (
                (key.lower().encode("utf-8"), value.encode("utf-8"))
                for key, value in self.request_data.headers.items()
            ),
            "client": self.client_connection.getpeername(),
            "server": (self.server_name, self.server_port),
        }

    def get_path(self) -> str:
        return self.request_data.path.split("?")[0]

    def get_query_string(self) -> bytes:
        query_string = self.request_data.path.split("?")
        if len(query_string) > 1:
            query_string = query_string[1]
            # query_string = urllib.parse.quote(query_string)
            query_string = query_string.encode("utf-8")
        else:
            query_string = b""
        return query_string

    def compile_headers(self):
        server_headers = [
            ("Date", formatdate(mktime(datetime.now().timetuple()))),
            ("Server", "Qactuar 0.0.1"),
        ]
        return self.response["headers"] + server_headers

    def finish_response(self):
        try:
            response_headers = self.compile_headers()
            response = f"HTTP/1.1 {self.response['status']}\r\n"
            for header in response_headers:
                response += "{}: {}\r\n".format(*header)
            body = self.response["body"].decode("utf-8")
            response += f"\r\n{body}"
            self.client_connection.sendall(response.encode("utf-8"))
        finally:
            self.close_socket()

    def close_socket(self):
        try:
            self.client_connection.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        self.client_connection.close()


def make_server(host, port, application):
    server = QactuarServer((host, port))
    server.set_app(application)
    return server


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit("Provide a ASGI application object as module:callable")
    app_path = sys.argv[1]
    module, app = app_path.split(":")
    module = __import__(module)
    app = getattr(module, app)
    httpd = make_server("127.0.0.1", 8000, app)
    httpd.serve_forever()
