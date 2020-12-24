import multiprocessing
import select
import socket
from time import time
from typing import Callable

from qactuar.processes.simple_child import make_child
from qactuar.servers.base import BaseQactuarServer


class SimpleForkServer(BaseQactuarServer):
    def serve_forever(self) -> None:
        try:
            while True:
                self.select_socket(self.listen_socket, process_handler=make_child)
                self.check_processes()
        except KeyboardInterrupt:
            self.shut_down()
        except Exception as err:
            self.exception_log.exception(err)

    def select_socket(
        self, listening_socket: socket.socket, process_handler: Callable
    ) -> None:
        ready_to_read, _, _ = select.select(
            [listening_socket], [], [], self.config.SELECT_SLEEP_TIME
        )
        if ready_to_read:
            accepted_socket = self.accept_client_connection(listening_socket)
            if accepted_socket:
                self.fork(accepted_socket, process_handler)

    def fork(self, client_socket: socket.socket, process_handler: Callable) -> None:
        process = multiprocessing.Process(
            target=process_handler, args=(self, client_socket)
        )
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
        if current_time - last_time > self.config.CHECK_PROCESS_INTERVAL:
            self.time_last_cleaned_processes = current_time
            for ident, process in list(self.processes.items()):
                if not process.is_alive():
                    process.close()
                    del self.processes[ident]

