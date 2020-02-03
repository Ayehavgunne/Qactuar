from dataclasses import dataclass, field
from typing import List, Tuple


@dataclass
class Response:
    status: bytes = b"200 OK"
    headers: List[Tuple[str, str]] = field(default_factory=list)
    body: bytes = b""
