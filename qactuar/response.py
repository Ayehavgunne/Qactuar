from dataclasses import dataclass, field
from typing import List, Tuple

from qactuar.util import BytesList


@dataclass
class Response:
    status: bytes = b"200"
    headers: List[Tuple[bytes, bytes]] = field(default_factory=list)
    body: BytesList = field(default_factory=BytesList)
