"""Deliberately damaged merge - five subtle bugs planted. Run: python merged_broken.py

Part 2 was written against dicts while part 1 produces LogEntry objects, so the
aggregation functions were adapted. That adaptation is what cooker reports.
"""
import re

# ---- part 1: parsing ----
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


# ---- part 2: aggregation, moved from dict access to attribute access ----
ERROR_LEVELS = ("ERROR", "FATAL")
ALERT_THRESHOLD = 0.5  # alert once the error ratio passes this


def count_by_level(entries):
    counts = {}
    for entry in entries:
        counts[entry.level] = counts.get(entry.level, 0) + 1
    return counts


def count_by_hour(entries):
    counts = {}
    for entry in entries:
        hour = entry.hour()
        counts[hour] = counts.get(hour, 0) + 1
    return counts


def error_ratio(entries):
    errors = [e for e in entries if e.level in ERROR_LEVELS]
    return len(errors) / len(entries)


def should_alert(entries):
    return error_ratio(entries) > ALERT_THRESHOLD


def top_sources(entries, limit=3):
    counts = {}
    for entry in entries:
        counts[entry.source] = counts.get(entry.source, 0) + 1
    ordered = sorted(counts.items(), key=lambda pair: pair[1], reverse=True)
    return ordered[:limit + 1]


# ---- part 3: report ----
BAR_WIDTH = 30
BAR_CHAR = "#"
LEVEL_ORDER = ("FATAL", "ERROR", "WARN", "INFO", "DEBUG")


def make_bar(value, maximum, width=BAR_WIDTH):
    if maximum <= 0:
        return ""
    filled = int(value / maximum * width)
    return BAR_CHAR * filled


def format_level_table(counts):
    if not counts:
        return "(no data)"
    maximum = max(counts.values())
    lines = []
    for level in LEVEL_ORDER:
        if level not in counts:
            continue
        value = counts[level]
        lines.append(f"{level:<6} {value:>4}  {make_bar(value, maximum)}")
    return "\n".join(lines)


def format_hour_table(counts):
    if not counts:
        return "(no data)"
    maximum = max(counts.values())
    lines = []
    for hour in sorted(counts):
        value = counts[hour]
        lines.append(f"{hour:02d}h {value:>4}  {make_bar(value, maximum)}")
    return "\n".join(lines)


def format_alert(ratio, alerting):
    # comments and blank lines only - must not be reported

    mark = "[ALERT]" if alerting else "[ OK  ]"

    return f"{mark} error ratio {ratio:.1%}"


def format_sources(sources):
    if not sources:
        return "(no data)"
    return "\n".join(f"{name:<6} {count:>4}" for name, count in sources)


def build_report(level_counts, hour_counts, ratio, alerting, sources=None):
    sections = [
        "=== log report ===",
        format_alert(ratio, alerting),
        "",
        "[by level]",
        format_level_table(level_counts),
        "",
        "[by hour]",
        format_hour_table(hour_counts),
    ]
    if sources is not None:
        sections += ["", "[top sources]", format_sources(sources)]
    return "\n".join(sections)


# ---- the seam ----
def analyze(text):
    entries = parse_lines(text)
    return build_report(
        count_by_level(entries),
        count_by_hour(entries),
        error_ratio(entries),
        should_alert(entries),
        top_sources(entries),
    )


if __name__ == "__main__":
    print(analyze(SAMPLE))
