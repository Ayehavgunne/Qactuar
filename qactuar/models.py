from typing import Any, Awaitable, Callable, List, MutableMapping, Tuple

BasicHeaders = List[Tuple[bytes, bytes]]
Scope = MutableMapping[str, Any]
Message = MutableMapping[str, Any]

Receive = Callable[[], Awaitable[Message]]
Send = Callable[[Message], Awaitable[None]]
ASGIApp = Callable[[Scope, Receive, Send], Awaitable[None]]
