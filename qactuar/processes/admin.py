import socket
from typing import TYPE_CHECKING

from qactuar.processes.base import BaseProcessHandler

if TYPE_CHECKING:
    from qactuar import QactuarServer


class AdminProcess(BaseProcessHandler):
    def __init__(self, server: "QactuarServer", admin_socket: socket.socket):
        super().__init__(server, admin_socket)

    def handle_request(self) -> None:
        print(self.request_data.body)


def make_admin(server: "QactuarServer", admin_socket: socket.socket) -> None:
    admin = AdminProcess(server, admin_socket)
    admin.start()
