"""Part 1 - log line parsing. Run: python part1_parse.py"""
import re

LOG_PATTERN = re.compile(
    r"^(?P<date>\d{4}-\d{2}-\d{2})\s+(?P<time>\d{2}:\d{2}:\d{2})\s+"
    r"(?P<level>[A-Z]+)\s+(?P<source>\S+)\s+(?P<message>.*)$"
)

VALID_LEVELS = ("DEBUG", "INFO", "WARN", "ERROR", "FATAL")

SAMPLE = """2026-09-05 09:12:01 INFO api request handled
2026-09-05 09:12:04 WARN db pool at 80%
2026-09-05 09:13:22 ERROR api timeout
garbage line
2026-09-05 10:01:00 ERROR db connection failed
2026-09-05 10:02:11 INFO api retry succeeded"""


class LogEntry:
    def __init__(self, date, time, level, source, message):
        self.date = date
        self.time = time
        self.level = level
        self.source = source
        self.message = message

    def hour(self):
        return int(self.time.split(":")[0])

    def __repr__(self):
        return f"<LogEntry {self.date} {self.time} {self.level} {self.source}>"


def parse_line(line):
    match = LOG_PATTERN.match(line.strip())
    if not match:
        return None
    parts = match.groupdict()
    if parts["level"] not in VALID_LEVELS:
        return None
    return LogEntry(parts["date"], parts["time"], parts["level"], parts["source"], parts["message"])


def parse_lines(text):
    entries = []
    for line in text.splitlines():
        entry = parse_line(line)
        if entry is not None:
            entries.append(entry)
    return entries


if __name__ == "__main__":
    parsed = parse_lines(SAMPLE)
    print(f"parsed {len(parsed)} of {len(SAMPLE.splitlines())} lines")
    for item in parsed:
        print(" ", item)
