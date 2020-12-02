from pathlib import Path
from typing import Optional

from .arguments import Arguments


class State:
    arguments: Optional[Arguments]

    def __init__(self) -> None:
        self.arguments = None

    @property
    def base_dir(self) -> Path:
        assert self.arguments
        return Path(self.arguments.base_dir)

    @property
    def critic_wheel(self) -> Path:
        assert self.arguments
        if self.arguments.critic_wheel:
            return Path(self.arguments.critic_wheel)
        for path in self.base_dir.glob("critic-*.whl"):
            return path
        raise Exception("No Critic wheel found!")


STATE = State()
