async def app(scope, receice, send):
    await send({"type": "http_response.start", "status": "200", "headers": []})
    await send(
        {
            "type": "http.response.body",
            "body": b"Hello, how are you?",
            "more_body": False,
        }
    )
