from tonberry import File, create_app, expose
from tonberry.content_types import TextHTML, TextPlain


class Root:
    @expose.get
    async def index(self) -> TextPlain:
        return "Hello, how are you?"

    @expose.get
    async def what(self, thing, num) -> TextPlain:
        return f"Hello {thing} {num}"

    @expose.post
    async def what(self, thing, num) -> TextPlain:
        return f"Go away {thing} {num}"

    @expose.get
    async def li(self) -> TextHTML:
        return File("../tests/lorem_ipsum.html")


app = create_app(Root)
