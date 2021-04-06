from typing import Sequence


def decode(encodings: Sequence[str], value: bytes) -> str:
    for encoding in encodings[:-1]:
        try:
            return value.decode(encoding)
        except UnicodeDecodeError:
            pass
    return value.decode(encodings[-1], errors="replace")
