import asyncio
import socket
from multiprocessing.queues import Queue
from queue import Empty
from typing import TYPE_CHECKING, List

if TYPE_CHECKING:
    from qactuar.servers.base import BaseQactuarServer


class PreForkChild:
    def __init__(self, server: "BaseQactuarServer", queue: Queue):
        self.loop = asyncio.new_event_loop()
        self.client_sockets: List[socket.socket] = []
        self.server = server
        self.queue = queue

    def start(self) -> None:
        while True:
            try:
                fd = self.queue.get_nowait()
            except Empty:
                pass
            else:
                self.client_sockets.append(
                    socket.fromfd(
                        fd, self.server.address_family, self.server.socket_type
                    )
                )


def make_child(server: "BaseQactuarServer", queue: Queue) -> None:
    child = PreForkChild(server, queue)
    child.start()
