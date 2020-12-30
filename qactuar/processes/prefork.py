import sys
from multiprocessing.queues import Queue
from queue import Empty
from typing import TYPE_CHECKING

from qactuar.processes.base import BaseProcessHandler

if TYPE_CHECKING:
    from qactuar.servers.prefork import PreForkServer


class PreForkChild(BaseProcessHandler):
    def __init__(self, server: "PreForkServer", queue: Queue):
        super().__init__(server)
        self.server = server
        self.queue = queue

    async def start(self) -> None:
        while True:
            try:
                ready = self.queue.get(timeout=0.001)
            except Empty:
                pass
            else:
                if ready:
                    client_socket = await self.server.async_accept_client_connection()
                    if client_socket:
                        client_socket = self.setup_ssl(client_socket)
                        await self.handle_request(client_socket)


def make_child(server: "PreForkServer", queue: Queue) -> None:
    child = PreForkChild(server, queue)
    try:
        child.loop.run_until_complete(child.start())
    except KeyboardInterrupt:
        sys.exit(0)
