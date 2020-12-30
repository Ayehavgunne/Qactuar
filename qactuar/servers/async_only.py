import select

from qactuar import ASGIApp, Config
from qactuar.processes.async_only import make_child
from qactuar.servers.base import BaseQactuarServer


class AsyncOnlyServer(BaseQactuarServer):
    def __init__(
        self,
        host: str = None,
        port: int = None,
        app: ASGIApp = None,
        config: Config = None,
    ):
        super().__init__(host, port, app, config)

    def serve_forever(self) -> None:
        self.start_up()
        self.loop.run_until_complete(self._serve_forever())

    async def _serve_forever(self) -> None:
        try:
            while True:
                await self.select_socket()
        except KeyboardInterrupt:
            await self.async_shut_down()
        except Exception as err:
            self.exception_log.exception(err)
            await self.async_shut_down()

    async def select_socket(self) -> None:
        ready_to_read, _, _ = select.select(
            [self.listen_socket], [], [], self.config.SELECT_SLEEP_TIME
        )
        if ready_to_read:
            client_socket = await self.async_accept_client_connection()
            if client_socket:
                await make_child(self, client_socket)
