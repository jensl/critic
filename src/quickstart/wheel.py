import glob
import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)

from .execute import execute
from .outputmanager import activity
from .system import System


def find(state_dir: str) -> Optional[str]:
    wheels = glob.glob(os.path.join(state_dir, "critic-*.whl"))
    if not wheels:
        return None
    if len(wheels) > 1:
        raise Exception("Multiple critic-*.whl files found!")
    return wheels[0]


async def build(system: System, current_mtime: float) -> str:
    wheel = find(system.state_dir)

    if wheel:
        if os.stat(wheel).st_mtime < current_mtime:
            logger.debug("wheel: needs rebuilding")
        else:
            logger.debug("wheel: is up-to-date")
            return wheel

    with activity("Building wheel"):
        await execute(
            "pip",
            "wheel",
            "--no-deps",
            f"--wheel-dir={system.state_dir}",
            system.arguments.root_dir,
        )

    wheel = find(system.state_dir)

    assert wheel
    return wheel
