import asyncio
import fnmatch
import logging
import os

logger = logging.getLogger(__name__)


class LogFilesFollower:
    def __init__(self, path, pattern):
        super().__init__()
        self.daemon = True
        self.path = path
        self.pattern = pattern
        self.seen = {}

    def __list(self):
        files = []
        for filename in os.listdir(self.path):
            if fnmatch.fnmatch(filename, self.pattern):
                size = os.path.getsize(os.path.join(self.path, filename))
                files.append((filename, size))
        return files

    def __check(self):
        for filename, size in self.__list():
            seen = self.seen.get(filename, 0)
            if size > seen:
                path = os.path.join(self.path, filename)
                with open(path, "r", encoding="utf-8") as logfile:
                    logfile.seek(seen)
                    contents = logfile.read()
                while True:
                    line, linebreak, contents = contents.partition("\n")
                    if not linebreak:
                        break
                    logger.info("%s: %s", filename, line)
                self.seen[filename] = size - len(contents)

    async def run(self):
        self.seen.update(self.__list())
        while True:
            self.__check()
            await asyncio.sleep(1)

    def start(self):
        async def done(fut):
            try:
                await fut
            except Exception:
                logger.exception("Log files follower crashed!")

        asyncio.create_task(self.run()).add_done_callback(done)
