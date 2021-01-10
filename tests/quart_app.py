from quart import Quart, websocket

app = Quart(__name__)


@app.route("/")
async def index():
    return "Hello from Quart"


@app.websocket("/ws_test")
async def ws_test():
    while True:
        data = await websocket.receive()
        await websocket.send(f"echo {data}")
