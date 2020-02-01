import errno
import os
import signal
import socket
import sys
from io import StringIO


def grim_reaper(signum, frame):
    while True:
        try:
            pid, status = os.waitpid(-1, os.WNOHANG,)
            print(
                "Child {pid} terminated with status {status}"
                "\n".format(pid=pid, status=status)
            )
        except OSError:
            return

        if pid == 0:
            return


class WSGIServer(object):

    address_family = socket.AF_INET
    socket_type = socket.SOCK_STREAM
    request_queue_size = 1024

    def __init__(self, server_address):
        self.listen_socket = listen_socket = socket.socket(
            self.address_family, self.socket_type
        )
        listen_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        listen_socket.bind(server_address)
        listen_socket.listen(self.request_queue_size)
        host, port = self.listen_socket.getsockname()[:2]
        self.server_name = socket.getfqdn(host)
        self.server_port = port
        self.headers_set = []
        self.application = None
        self.client_connection = None
        self.request_data = None
        self.request_method = None
        self.path = None
        self.request_version = None

    def set_app(self, application):
        self.application = application

    def serve_forever(self):
        listen_socket = self.listen_socket
        while True:
            try:
                self.client_connection, client_address = listen_socket.accept()
            except IOError as e:
                code, msg = e.args
                if code == errno.EINTR:
                    continue
                else:
                    raise

            pid = os.fork()
            if pid == 0:
                listen_socket.close()
                self.handle_one_request()
                os._exit(0)
            else:
                self.client_connection.close()

    def handle_one_request(self):
        self.request_data = request_data = self.client_connection.recv(1024)
        print("".join(f"< {line}\n" for line in request_data.splitlines()))
        self.parse_request(request_data)
        env = self.get_environ()
        result = self.application(env, self.start_response)
        self.finish_response(result)

    def parse_request(self, text):
        request_line = text.splitlines()[0]
        request_line = request_line.rstrip(b"\r\n")
        (self.request_method, self.path, self.request_version,) = request_line.split()

    def get_environ(self):
        env = {
            "wsgi.version": (1, 0),
            "wsgi.url_scheme": "http",
            "wsgi.input": StringIO(self.request_data.decode("utf-8")),
            "wsgi.errors": sys.stderr,
            "wsgi.multithread": False,
            "wsgi.multiprocess": False,
            "wsgi.run_once": False,
            "REQUEST_METHOD": self.request_method,
            "PATH_INFO": self.path,
            "SERVER_NAME": self.server_name,
            "SERVER_PORT": str(self.server_port),
        }
        return env

    def start_response(self, status, response_headers, _=None):
        server_headers = [
            ("Date", "Tue, 31 Mar 2015 12:54:48 GMT"),
            ("Server", "WSGIServer 0.2"),
        ]
        self.headers_set = [status, response_headers + server_headers]
        # To adhere to WSGI specification the start_response must return
        # a 'write' callable. We simplicity's sake we'll ignore that detail
        # for now.
        # return self.finish_response

    def finish_response(self, result):
        try:
            status, response_headers = self.headers_set
            response = f"HTTP/1.1 {status}\r\n"
            for header in response_headers:
                response += "{0}: {1}\r\n".format(*header)
            response += "\r\n"
            for data in result:
                response += data.decode("utf-8")
            print("".join(f"> {line}\n" for line in response.splitlines()))
            self.client_connection.sendall(response.encode("utf-8"))
        finally:
            self.client_connection.close()


SERVER_ADDRESS = (HOST, PORT) = "", 8888


def make_server(server_address, application):
    signal.signal(signal.SIGCHLD, grim_reaper)
    server = WSGIServer(server_address)
    server.set_app(application)
    return server


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit("Provide a WSGI application object as module:callable")
    app_path = sys.argv[1]
    module, app = app_path.split(":")
    module = __import__(module)
    app = getattr(module, app)
    httpd = make_server(SERVER_ADDRESS, app)
    print(f"WSGIServer: Serving HTTP on {HOST}:{PORT} ...\n")
    httpd.serve_forever()
