import multiprocessing

# import select
import socket
from time import time
from typing import Optional

from qactuar import ASGIApp, Config
from qactuar.processes.simple_fork import make_child
from qactuar.servers.base import BaseQactuarServer


class SimpleForkServer(BaseQactuarServer):
    def __init__(
        self,
        host: str = None,
        port: int = None,
        app: ASGIApp = None,
        config: Config = None,
    ):
        super().__init__(host, port, app, config)
        self.time_last_cleaned_processes: float = time()

    async def serve_forever(self) -> None:
        while True:
            client_socket = await self.select_socket()
            if client_socket:
                self.fork(client_socket)
            self.check_processes()
            if self.shutting_down:
                break

    async def select_socket(self) -> Optional[socket.socket]:
        ready_to_read = await self.loop.run_in_executor(None, self.watch_socket)
        if ready_to_read:
            return await self.accept_client_connection()

    def fork(self, client_socket: socket.socket) -> None:
        process = multiprocessing.Process(target=make_child, args=(self, client_socket))
        process.daemon = True
        try:
            process.start()
        except AttributeError as err:
            self.exception_log.exception(err)
            self.server_log.warning(f"Could not start process {process.ident}")
        else:
            ident = process.ident
            if ident:
                self.processes[ident] = process

    def check_processes(self) -> None:
        current_time = time()
        last_time = self.time_last_cleaned_processes
        if current_time - last_time > 1:
            self.time_last_cleaned_processes = current_time
            for ident, process in list(self.processes.items()):
                if not process.is_alive():
                    process.close()
                    del self.processes[ident]
