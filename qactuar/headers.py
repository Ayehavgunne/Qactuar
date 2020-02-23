from typing import Dict, Optional, Union

from qactuar.models import BasicHeaders


class Headers:
    def __init__(self, headers: BasicHeaders = None):
        if headers is None:
            headers = []
        self._headers = headers
        self._header_dict: Dict[str, str] = {}
        self.decode()

    def __contains__(self, item: str) -> bool:
        if item in self._header_dict:
            return True
        return False

    def __getitem__(self, item: str) -> Optional[str]:
        if item in self._header_dict:
            return self._header_dict[item]
        return None

    def __setitem__(self, key: str, value: Union[str, int]) -> None:
        self._header_dict[key] = str(value)

    def __delitem__(self, key: str) -> None:
        del self._header_dict[key]

    def decode(self) -> None:
        for key, value in self._headers:
            self._header_dict[key.decode("utf-8")] = value.decode("utf-8")
