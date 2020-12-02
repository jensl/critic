from typing import Optional


class BooleanWithReason:
    def __init__(self, reason: Optional[str] = None):
        self.__reason = reason

    def __bool__(self) -> bool:
        return self.__reason is None

    @property
    def reason(self) -> str:
        assert self.__reason is not None
        return self.__reason
