import asyncio
import socket
import sys
from multiprocessing.queues import Queue
from queue import Empty
from typing import TYPE_CHECKING, Any, Dict, List

from qactuar.exceptions import HTTPError
from qactuar.handlers import HTTPHandler
from qactuar.processes.base import BaseProcessHandler
from qactuar.request import Request
from qactuar.response import Response

if TYPE_CHECKING:
    from qactuar.servers.base import BaseQactuarServer


class PreForkChild(BaseProcessHandler):
    def __init__(self, server: "BaseQactuarServer", queue: Queue):
        super().__init__(server)
        self.loop = asyncio.new_event_loop()
        self.client_sockets: List[socket.socket] = []
        self.server = server
        self.queue = queue
        self.http_handler = HTTPHandler(server)

    def start(self, *args: List[Any], **kwargs: Dict[str, Any]) -> None:
        while True:
            try:
                ready = self.queue.get_nowait()
            except Empty:
                pass
            else:
                if ready:
                    client_socket = self.server.accept_client_connection()
                    if client_socket:
                        self.client_sockets.append(client_socket)
                        request = self.get_request_data(client_socket)
                        self.handle_request(client_socket, request)

    def handle_request(
        self, client_socket: socket.socket, request: Request
    ) -> Response:
        response = Response(request=request)
        if not request.raw_request:
            self.close_socket(client_socket, request)
            return response
        try:
            response = self.send_to_app(request)
        except KeyboardInterrupt:
            sys.exit(0)
        except HTTPError as err:
            response.status = str(err.args[0]).encode("utf-8")
            response.body.write(str(err.args[0]).encode("utf-8"))
        except Exception as err:
            self.exception_log.exception(err, extra={"request_id": request.request_id})
            response.status = b"500"
            response.body.write(b"Internal Server Error")
        finally:
            if response:
                self.log_access(request, response)
            self.finish_response(client_socket, response)
        return response

    def send_to_app(self, request: Request) -> Response:
        self.loop.create_task(
            self.get_app(request)(
                self.http_handler.create_scope(),
                self.http_handler.receive,
                self.http_handler.send,
            )
        )
        return self.http_handler.response

    def close_socket(self, client_socket: socket.socket, request: Request) -> None:
        self.http_handler.closing = True
        try:
            self.send_to_app(request)
        except HTTPError:
            pass
        super().close_socket(client_socket, request)


def make_child(server: "BaseQactuarServer", queue: Queue) -> None:
    child = PreForkChild(server, queue)
    child.start()
