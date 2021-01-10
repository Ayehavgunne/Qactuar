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

    async def serve_forever(self) -> None:
        while True:
            await self.select_socket()
            if self.shutting_down:
                break

    async def select_socket(self) -> None:
        ready_to_read = await self.loop.run_in_executor(None, self.watch_socket)
        if ready_to_read:
            client_socket = await self.accept_client_connection()
            if client_socket:
                await make_child(self, client_socket)
