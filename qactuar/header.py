from typing import Dict, Optional, Union

from qactuar.models import Headers


class Header:
    def __init__(self, header: Headers = None):
        if header is None:
            header = []
        self._header = header
        self._header_attrs: Dict[str, str] = {}
        self.decode()

    def __contains__(self, item: str) -> bool:
        if item in self._header_attrs:
            return True
        return False

    def __getitem__(self, item: str) -> Optional[str]:
        if item in self._header_attrs:
            return self._header_attrs[item]
        return None

    def __setitem__(self, key: str, value: Union[str, int]) -> None:
        self._header_attrs[key] = str(value)

    def __delitem__(self, key: str) -> None:
        del self._header_attrs[key]

    def decode(self) -> None:
        for key, value in self._header:
            self._header_attrs[key.decode("utf-8")] = value.decode("utf-8")
