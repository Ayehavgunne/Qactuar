from dataclasses import dataclass
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


@dataclass
class ProcStat:
    minor_faults: int = 0
    major_faults: int = 0
    user_time: int = 0
    system_time: int = 0
    virtual_size: int = 0
    resident_set_size: int = 0


@dataclass
class IoStat:
    read_char: int = 0
    write_char: int = 0
    read_bytes: int = 0
    write_bytes: int = 0


@dataclass
class MemStat:
    file_desc_size: int = 0
    vm_peak: int = 0
    vm_size: int = 0
    vm_highwm: int = 0
    vm_rss: int = 0
    vm_data: int = 0
    vm_lib: int = 0
    vm_pte: int = 0
    threads: int = 0


def parse_proc_stat_line(stat_line: str) -> ProcStat:
    parts = stat_line.split(" ")
    return ProcStat(
        minor_faults=int(parts[9]),
        major_faults=int(parts[11]),
        user_time=int(parts[13]),
        system_time=int(parts[14]),
        virtual_size=int(parts[22]),
        resident_set_size=int(parts[23]),
    )


io_stat_map = {
    "rchar": "read_char",
    "wchar": "write_char",
    "read_bytes": "read_bytes",
    "write_bytes": "write_bytes",
}


def parse_proc_io_line(io_line: str) -> IoStat:
    io_stat = IoStat()

    parts = io_line.split("\n")
    for part in parts:
        stat_parts = part.split(": ")
        if len(stat_parts) == 2:
            key, value = stat_parts
            if key in io_stat_map:
                setattr(io_stat, io_stat_map[key], int(value))

    return io_stat


mem_stat_map = {
    "FDSize": "file_desc_size",
    "VmPeak": "vm_peak",
    "VmSize": "vm_size",
    "VmHWM": "vm_highwm",
    "VmRSS": "vm_rss",
    "VmData": "vm_data",
    "VmLib": "vm_lib",
    "VmPTE": "vm_pte",
    "Threads": "threads",
}


def parse_proc_mem_line(mem_line: str) -> MemStat:
    mem_stat = MemStat()

    parts = mem_line.split("\n")
    for part in parts:
        stat_parts = part.split(":\t")
        if len(stat_parts) == 2:
            key, value = stat_parts
            if key in mem_stat_map:
                value = value.replace("kB", "")
                setattr(mem_stat, mem_stat_map[key], int(value))

    return mem_stat
