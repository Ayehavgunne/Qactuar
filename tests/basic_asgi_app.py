async def app(scope, receive, send) -> None:
    if scope["type"] == "lifespan":
        while True:
            message = await receive()
            if message["type"] == "lifespan.startup":
                await send({"type": "lifespan.startup.complete"})
            elif message["type"] == "lifespan.shutdown":
                await send({"type": "lifespan.shutdown.complete"})
                return
    else:
        await send({"type": "http_response.start", "status": "200", "headers": []})
        await send(
            {
                "type": "http.response.body",
                "body": b"Hello, how are you?",
                "more_body": False,
            }
        )
