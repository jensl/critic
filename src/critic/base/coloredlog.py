import logging

BLACK, RED, GREEN, YELLOW, BLUE, MAGENTA, CYAN, WHITE = range(8)

# The background is set with 40 plus the number of the color, and the foreground with 30

# These are the sequences need to get colored ouput
RESET_SEQ = "\033[0m"
COLOR_SEQ = "\033[1;%dm"
BOLD_SEQ = "\033[1m"

FOREGROUND = {
    "WARNING": BLACK,
    "INFO": WHITE,
    "DEBUG": BLUE,
    "STDOUT": MAGENTA,
    "STDERR": CYAN,
    "CRITICAL": YELLOW,
    "ERROR": WHITE,
}
BACKGROUND = {
    "ERROR": RED,
    "WARNING": YELLOW,
}


class Formatter(logging.Formatter):
    def __init__(self, msg):
        super().__init__(f"%(color)s{msg}%(reset)s")

    def format(self, record):
        color = ""
        if record.levelname in FOREGROUND:
            color += COLOR_SEQ % (30 + FOREGROUND[record.levelname])
        if record.levelname in BACKGROUND:
            color += COLOR_SEQ % (40 + BACKGROUND[record.levelname])
        record.color = color
        record.reset = RESET_SEQ if color else ""
        return super().format(record)

    @staticmethod
    def is_supported():
        return True
        # import curses

        # curses.initscr()
        # result = curses.can_change_color()
        # curses.endwin()

        # return result


__all__ = ["Formatter"]
