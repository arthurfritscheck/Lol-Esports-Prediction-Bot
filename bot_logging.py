import logging
import os
import sys
from datetime import datetime

import discord


class Tee:
    """Writes everything to the console and to a log file, with a timestamp in front of every line in the file."""

    def __init__(self, stream, log_file):
        self.stream = stream
        self.log_file = log_file
        self.at_line_start = True

    def write(self, data):
        if self.stream is not None:
            try:
                self.stream.write(data)
            except Exception:
                pass
        for chunk in data.splitlines(keepends=True):
            if self.at_line_start:
                self.log_file.write(datetime.now().strftime('[%Y-%m-%d %H:%M:%S] '))
            self.log_file.write(chunk)
            self.at_line_start = chunk.endswith('\n')
        self.log_file.flush()
        return len(data)

    def flush(self):
        if self.stream is not None:
            self.stream.flush()
        self.log_file.flush()

    def isatty(self):
        # tells discord.py not to use colour codes, which would end up as garbage in the log file
        return False


def disable_console_quick_edit():
    """
    Clicking inside a windows console window starts 'Select' mode, which pauses every program writing to it.
    For the bot that means a frozen event loop and 'The application did not respond' in discord, so turn it off.
    """
    if sys.platform != 'win32':
        return
    try:
        import ctypes
        kernel32 = ctypes.windll.kernel32
        handle = kernel32.GetStdHandle(-10)  # STD_INPUT_HANDLE
        mode = ctypes.c_uint32()
        if kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
            ENABLE_QUICK_EDIT_MODE = 0x0040
            ENABLE_EXTENDED_FLAGS = 0x0080
            kernel32.SetConsoleMode(handle, (mode.value & ~ENABLE_QUICK_EDIT_MODE) | ENABLE_EXTENDED_FLAGS)
    except Exception as e:
        print(f"Could not disable console quick edit mode: {e}")


def setup_logging(test_mode):
    disable_console_quick_edit()

    # the windows console can't print emoji in usernames by default, which would crash the print calls
    for stream in (sys.stdout, sys.stderr):
        if stream is not None and hasattr(stream, 'reconfigure'):
            stream.reconfigure(encoding='utf-8', errors='replace')

    log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'logs')
    os.makedirs(log_dir, exist_ok=True)
    log_path = os.path.join(log_dir, 'test-bot.log' if test_mode else 'bot.log')
    log_file = open(log_path, 'a', encoding='utf-8')
    sys.stdout = Tee(sys.stdout, log_file)
    sys.stderr = Tee(sys.stderr, log_file)

    # discord.py's own messages (reconnects, rate limits, errors in events) end up in the same console and log file
    # no time in the format, the log file already gets a timestamp per line
    formatter = logging.Formatter('[{levelname}] {name}: {message}', style='{')
    discord.utils.setup_logging(handler=logging.StreamHandler(sys.stderr), formatter=formatter, level=logging.INFO, root=False)
    print(f"Logging to {log_path}")
