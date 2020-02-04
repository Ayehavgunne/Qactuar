from typing import List


class BytesList:
    def __init__(self):
        self._bytes_list: List[bytes] = []

    def write(self, new_bytes: bytes) -> None:
        self._bytes_list.append(new_bytes)

    def writelines(self, bytes_list: List[bytes]) -> None:
        self._bytes_list.extend(bytes_list)

    def read(self) -> bytes:
        return b"".join(self._bytes_list)

    def __contains__(self, item):
        return item in self.read()
