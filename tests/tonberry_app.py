from asyncio import sleep

from tonberry import create_app, expose, websocket
from tonberry.content_types import TextHTML, TextPlain
from tonberry.util import File


class Root:
    @expose.get
    async def index(self) -> TextPlain:
        return "Hello, how are you?"

    @expose.get
    async def what(self, thing, num) -> TextPlain:
        return f"Hello {thing} {num}"

    @expose.post
    async def what(self, thing=None, num=None) -> TextPlain:
        return f"Go away {thing} {num}"

    @expose.get
    async def li(self) -> TextHTML:
        return File("../tests/lorem_ipsum.html")

    @expose.websocket
    async def ws_test(self) -> None:
        while True:
            msg = await websocket.receive_text()
            print(msg)
            await sleep(3)
            await websocket.send_text(msg)


app = create_app(Root)
