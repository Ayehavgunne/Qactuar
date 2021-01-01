import multiprocessing
import select
import socket
from time import time

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

    def serve_forever(self) -> None:
        self.start_up()
        try:
            while True:
                self.select_socket()
                self.check_processes()
        except KeyboardInterrupt:
            self.shut_down()
        except Exception as err:
            self.exception_log.exception(err)
            self.shut_down()

    def select_socket(self) -> None:
        ready_to_read, _, _ = select.select(
            [self.listen_socket], [], [], self.config.SELECT_SLEEP_TIME
        )
        if ready_to_read:
            accepted_socket = self.accept_client_connection()
            if accepted_socket:
                self.fork(accepted_socket)

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
