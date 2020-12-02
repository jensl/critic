from typing import Optional, Protocol


class Arguments(Protocol):
    base_dir: str
    critic_wheel: Optional[str]
