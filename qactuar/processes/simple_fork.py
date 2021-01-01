import socket
from typing import TYPE_CHECKING

from qactuar.processes.base import BaseProcessHandler

if TYPE_CHECKING:
    from qactuar.servers.simple_fork import SimpleForkServer


class ChildProcess(BaseProcessHandler):
    def __init__(self, server: "SimpleForkServer"):
        super().__init__(server)

    async def start(self, client_socket: socket.socket = None) -> None:
        if not client_socket:
            return
        client_socket = self.setup_ssl(client_socket)
        await self.handle_request(client_socket)


def make_child(server: "SimpleForkServer", client_socket: socket.socket) -> None:
    child = ChildProcess(server)
    child.loop.run_until_complete(child.start(client_socket))
