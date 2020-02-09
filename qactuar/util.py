from typing import List, Union


class BytesList:
    def __init__(self) -> None:
        self._bytes_list: List[bytes] = []

    def write(self, new_bytes: bytes) -> None:
        self._bytes_list.append(new_bytes)

    def writelines(self, *bytes_list: Union[bytes, List[bytes]]) -> None:
        if len(bytes_list) == 1:
            if isinstance(bytes_list[0], (list, tuple)):
                bytes_list = bytes_list[0]  # type: ignore
        self._bytes_list.extend(bytes_list)  # type: ignore

    def read(self) -> bytes:
        return b"".join(self._bytes_list)

    def readlines(self) -> List[bytes]:
        return self._bytes_list

    def clear(self) -> None:
        self._bytes_list = []

    def __contains__(self, item: bytes) -> bool:
        return item in self.read()
