import socket
from typing import TYPE_CHECKING

from qactuar.processes.base import BaseProcessHandler

if TYPE_CHECKING:
    from qactuar.servers.async_only import AsyncOnlyServer


class AsyncOnlyChild(BaseProcessHandler):
    def __init__(self, server: "AsyncOnlyServer"):
        super().__init__(server)

    async def start(self, client_socket: socket.socket = None) -> None:
        if not client_socket:
            return
        client_socket = self.setup_ssl(client_socket)
        await self.handle_request(client_socket)


async def make_child(server: "AsyncOnlyServer", client_socket: socket.socket) -> None:
    child = AsyncOnlyChild(server)
    await child.start(client_socket)
