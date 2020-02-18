import struct
from typing import List, Optional, Union

from qactuar.exceptions import WebSocketError
from qactuar.util import BytesList, BytesReader


def bit_array_to_int(bits: List[int]) -> int:
    return int(int("".join([str(b) for b in bits]), 2))


def bytes_to_bit_array(byte: bytes) -> List[int]:
    return [int(b) for i in byte for b in bin(i)[2:]]


def int_to_bit_array(i: int) -> List[int]:
    return [int(b) for b in bin(i)[2:]]


def bit_array_z_fill(length: int, bit_array: List[int]) -> List[int]:
    while len(bit_array) < length:
        bit_array.insert(0, 0)
    return bit_array


class Opcodes:
    CONTINUES = [0, 0, 0, 0]
    UTF8_TEXT = [0, 0, 0, 1]
    BINARY = [0, 0, 1, 0]
    TERMINATE = [1, 0, 0, 0]
    PING = [1, 0, 0, 1]
    PONG = [1, 0, 1, 0]


class Frame:
    def __init__(self, data: bytes = None):
        self._data = data or bytes()
        self.data_reader = BytesReader(data)
        self.fin = 0
        self.rsv1 = 0
        self.rsv2 = 0
        self.rsv3 = 0
        self.opcode = []
        self.mask = 0
        self.payload_len = 0
        self.masking_key = bytes()
        self.payload = bytes()
        if self._data:
            bits = bytes_to_bit_array(self.data_reader.read(1))
            self.fin, self.rsv1, self.rsv2, self.rsv3, *self.opcode = bits
            bits = bytes_to_bit_array(self.data_reader.read(1))
            self.mask = bits[0]
            self.payload_len = self.get_payload_len(bits[1:])
            if self.mask:
                self.masking_key = self.data_reader.read(4)
            self.payload = self.data_reader.read(self.payload_len)
            if self.mask:
                self.payload = bytes(
                    [
                        item ^ self.masking_key[index % 4]
                        for index, item in enumerate(self.payload)
                    ]
                )

    def get_payload_len(self, bits: List[int]) -> int:
        first_length = bit_array_to_int(bits)
        if first_length < 126:
            return first_length
        elif first_length == 126:
            return struct.unpack("!H", self.data_reader.read(2))[0]
        elif first_length == 127:
            return struct.unpack("!Q", self.data_reader.read(8))[0]
        else:
            raise WebSocketError("Payload length is incorrect")

    @property
    def message(self) -> Union[str, bytes]:
        if self.opcode == Opcodes.BINARY:
            return self.payload
        return self.payload.decode("utf-8")

    @property
    def is_complete(self) -> bool:
        return len(self.payload) == self.payload_len and len(self._data) > 0

    @property
    def is_pong(self) -> bool:
        return self.opcode == Opcodes.PONG


class WebSocket:
    def __init__(self) -> None:
        self.read_frames: List[Frame] = []
        self.write_frames: List[bytes] = []

    @property
    def is_text(self) -> bool:
        if self.read_frames:
            return self.read_frames[0].opcode == Opcodes.UTF8_TEXT
        else:
            return False

    @property
    def is_binary(self) -> bool:
        if self.read_frames:
            return self.read_frames[0].opcode == Opcodes.BINARY
        else:
            return False

    @property
    def reading_complete(self) -> bool:
        if self.read_frames:
            return self.read_frames[-1].opcode != Opcodes.CONTINUES
        else:
            return False

    @property
    def should_terminate(self) -> bool:
        if self.read_frames:
            return self.read_frames[-1].opcode == Opcodes.TERMINATE
        else:
            return False

    @property
    def being_pinged(self) -> bool:
        if self.read_frames:
            return self.read_frames[-1].opcode == Opcodes.PING
        else:
            return False

    def add_read_frame(self, frame: Frame) -> None:
        self.read_frames.append(frame)

    def clear_frames(self) -> None:
        self.read_frames = []
        self.write_frames = []

    def read(self) -> Optional[Union[str, bytes]]:
        if self.is_text:
            return "".join(frame.payload.decode("utf-8") for frame in self.read_frames)
        if self.is_binary:
            return b"".join(frame.payload for frame in self.read_frames)
        return None

    def write(
        self,
        message: Union[str, bytes],
        terminate: bool = False,
        ping: bool = False,
        pong: bool = False,
    ) -> List[bytes]:
        pos = 0
        chunk_size = 32768
        frames: List[bytes] = []
        for section in [
            message[i : i + chunk_size] for i in range(0, len(message), chunk_size)
        ]:
            section_len = len(section)
            if isinstance(message, str):
                section = section.encode("utf-8")  # type: ignore
            fin = int(section_len < chunk_size)
            frame = BytesList()
            bit_array = [fin, 0, 0, 0]
            if terminate:
                bit_array.extend([1, 0, 0, 0])
            elif ping:
                bit_array.extend([1, 0, 0, 1])
            elif pong:
                bit_array.extend([1, 0, 1, 0])
            elif isinstance(message, str) and not frames:
                bit_array.extend([0, 0, 0, 1])
            elif isinstance(message, bytes) and not frames:
                bit_array.extend([0, 0, 1, 0])
            else:
                bit_array.extend([0, 0, 0, 0])
            first_bit = bit_array_to_int(bit_array)
            frame.write(bytes(bytearray([first_bit])))
            bit_array = [0]
            if section_len < 126:
                new_bits = bit_array_z_fill(7, int_to_bit_array(section_len))
                bit_array.extend(new_bits)
            elif section_len < 65536:
                pass  # TODO: write up to 16 bytes of data
            elif section_len < 9_223_372_036_854_775_808:
                pass  # TODO: write up to 64 bytes of data
            else:
                raise WebSocketError("This shouldn't happen")
            second_bit = bit_array_to_int(bit_array)
            frame.write(bytes(bytearray([second_bit])))
            frame.write(section)  # type: ignore
            frames.append(frame.read())
            pos += chunk_size
        self.write_frames = frames
        return frames

    @property
    def response(self) -> Optional[bytes]:
        if self.write_frames:
            return b"".join(self.write_frames)
        return None
