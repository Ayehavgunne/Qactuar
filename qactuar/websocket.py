import struct
from io import BytesIO
from typing import List, Optional, Union

from qactuar.exceptions import WebSocketError
from qactuar.header import Header


class Opcodes:
    CONTINUES = 0x00  # 0
    UTF8_TEXT = 0x01  # 1
    BINARY = 0x02  # 10
    TERMINATE = 0x08  # 1000
    PING = 0x09  # 1001
    PONG = 0x0A  # 1010


class Frame:
    def __init__(self, data: bytes = None):
        self._data = data or b""
        self.data = BytesIO(self._data)
        self.fin = False
        self.rsv1 = False
        self.rsv2 = False
        self.rsv3 = False
        self.opcode = bytes()
        self.mask = False
        self.payload_len = 0
        self.masking_key = bytes()
        self.payload = bytes()
        if self._data:
            bits1, bits2 = struct.unpack("!BB", self.data.read(2))
            self.fin = True if bits1 & 0b10000000 else False
            self.rsv1 = True if bits1 & 0b01000000 else False
            self.rsv2 = True if bits1 & 0b00100000 else False
            self.rsv3 = True if bits1 & 0b00010000 else False
            self.opcode = bits1 & 0b00001111
            self.mask = True if bits2 & 0b10000000 else False
            self.payload_len = self.get_payload_len(bits2 & 0b01111111)
            if self.mask:
                self.masking_key = self.data.read(4)
            else:
                raise WebSocketError("Client messages must be masked")
            self.payload = self.data.read(self.payload_len)
            self.data.close()
            self.payload = bytes(
                [
                    item ^ self.masking_key[index % 4]
                    for index, item in enumerate(self.payload)
                ]
            )

    def get_payload_len(self, length: int) -> int:
        if length < 126:
            return length
        elif length == 126:
            return struct.unpack("!H", self.data.read(2))[0]
        elif length == 127:
            return struct.unpack("!Q", self.data.read(8))[0]
        else:
            raise WebSocketError("Payload length is not valid")

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
        self.headers = Header()
        self.subprotocols: List[str] = []
        self.subprotocol = ""
        self.diconnect_code = 1000

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

    #    1000
    #       1000 indicates a normal closure, meaning that the purpose for
    #       which the connection was established has been fulfilled.
    #
    #    1001
    #       1001 indicates that an endpoint is "going away", such as a server
    #       going down or a browser having navigated away from a page.
    #
    #    1002
    #       1002 indicates that an endpoint is terminating the connection due
    #       to a protocol error.
    #
    #    1003
    #       1003 indicates that an endpoint is terminating the connection
    #       because it has received a type of data it cannot accept (e.g., an
    #       endpoint that understands only text data MAY send this if it
    #       receives a binary message).

    def write(
        self,
        message: Union[str, bytes] = b"",
        terminate: bool = False,
        ping: bool = False,
        pong: bool = False,
        close_status_code: int = 1000,
    ) -> List[bytes]:
        chunk_size = int((2 ** 32) / 8)
        frames: List[bytes] = []
        is_str = False
        if isinstance(message, str):
            is_str = True
            message = message.encode("utf-8")
        if not message and terminate:
            message = str(close_status_code).encode("utf-8")

        for section in [
            message[i : i + chunk_size] for i in range(0, len(message), chunk_size)
        ]:
            section_len = len(section)
            fin = section_len < chunk_size
            with BytesIO() as frame:
                bits = 0b00000000

                if fin:
                    bits |= 0b10000000
                if terminate:
                    bits |= 0b00001000
                elif ping:
                    bits |= 0b00001001
                elif pong:
                    bits |= 0b00001010
                elif is_str and not frames:
                    bits |= 0b00000001
                elif not is_str and not frames:
                    bits |= 0b00000010

                if section_len < 126:
                    frame.write(struct.pack("!BB", bits, section_len))
                elif section_len < 2 ** 16:
                    frame.write(struct.pack("!BBH", bits, 126, section_len))
                else:
                    frame.write(struct.pack("!BBQ", bits, 127, section_len))  # mmm bbq

                frame.write(section)
                frames.append(frame.getvalue())
        self.write_frames = frames
        return frames

    def pop_write_frame(self, index: int = -1) -> Optional[bytes]:
        if self.write_frames:
            return self.write_frames.pop(index)
        return None

    @property
    def response(self) -> Optional[bytes]:
        if self.write_frames:
            return b"".join(self.write_frames)
        return None
