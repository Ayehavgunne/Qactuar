import asyncio
import socket
import sys
from typing import TYPE_CHECKING

from qactuar.exceptions import HTTPError
from qactuar.qactuar_logger import create_http_access_logger
from qactuar.request import Request
from qactuar.util import BytesList

if TYPE_CHECKING:
    from qactuar import QactuarServer


class ChildProcess:
    def __init__(self, server: "QactuarServer"):
        self.loop = asyncio.new_event_loop()
        self.server = server
        self.logger = create_http_access_logger()

    def handle_one_request(self) -> None:
        try:
            self.get_request_data()
            if not self.server.raw_request_data:
                self.server.close_socket()
                return
            if (
                self.server.request_data.headers["Connection"]
                and self.server.request_data.headers["Upgrade"]
            ):
                self.server.websocket_handler.ws_shake_hand()
            self.loop.run_until_complete(
                self.server.app(
                    self.server.http_handler.create_scope(),
                    self.server.http_handler.receive,
                    self.server.http_handler.send,
                )
            )
        except KeyboardInterrupt:
            sys.exit(0)
        except HTTPError as err:
            self.server.response.status = str(err.args[0]).encode("utf-8")
            self.server.response.body.write(str(err.args[0]).encode("utf-8"))
        except Exception as err:
            self.server.logger.exception(err)
            self.server.response.status = b"500"
            self.server.response.body.write(b"wat happen?!")
        finally:
            if self.server.config.ACCESS_LOGGING:
                self.logger.access(
                    self.server.client_info,
                    self.server.request_data.path,
                    self.server.request_data.command,
                    self.server.request_data.request_version_num,
                    self.server.response.status,
                )
            self.server.finish_response()

    def get_request_data(self) -> None:
        request_data = BytesList()
        request = Request()

        if self.server.client_connection:
            while True:
                try:
                    request_data.write(
                        self.server.client_connection.recv(
                            self.server.config.RECV_BYTES
                        )
                    )
                except socket.timeout:
                    request.raw_request = request_data.read()
                    if request.headers_complete:
                        content_length = request.headers["content-length"]
                        if content_length is not None and request.command != "GET":
                            if len(request.body) == int(content_length):
                                break
                            else:
                                continue
                        break

        self.server.request_data = request
        self.server.raw_request_data = request_data.read()


def make_child(server: "QactuarServer") -> None:
    child = ChildProcess(server)
    child.handle_one_request()
