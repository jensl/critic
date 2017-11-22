import logging
import os
import py_compile

from .outputmanager import activity

logger = logging.getLogger(__name__)


class Compilation:
    @staticmethod
    def test() -> bool:
        with activity("Compiling all sources"):
            success = True
            for dirname, _, filenames in os.walk("critic"):
                for filename in filenames:
                    if filename[0] == ".":
                        continue
                    if not filename.endswith(".py"):
                        continue
                    path = os.path.join(dirname, filename)
                    try:
                        py_compile.compile(path, doraise=True)
                    except py_compile.PyCompileError as error:
                        logger.error("Failed to compile %s:\n%s", path, error)
                        success = False
            return success
