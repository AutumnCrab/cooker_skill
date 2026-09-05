"""Part 2 - aggregation. Built against plain dicts, not the LogEntry class from part 1.
This mismatch is exactly the kind of thing a merge has to resolve. Run: python part2_aggregate.py
"""

ERROR_LEVELS = ("ERROR", "FATAL")
ALERT_THRESHOLD = 0.3  # alert once the error ratio passes this


def count_by_level(entries):
    counts = {}
    for entry in entries:
        counts[entry["level"]] = counts.get(entry["level"], 0) + 1
    return counts


def count_by_hour(entries):
    counts = {}
    for entry in entries:
        hour = int(entry["time"].split(":")[0])
        counts[hour] = counts.get(hour, 0) + 1
    return counts


def error_ratio(entries):
    if not entries:
        return 0.0
    errors = [e for e in entries if e["level"] in ERROR_LEVELS]
    return len(errors) / len(entries)


def should_alert(entries):
    return error_ratio(entries) >= ALERT_THRESHOLD


def top_sources(entries, limit=3):
    counts = {}
    for entry in entries:
        counts[entry["source"]] = counts.get(entry["source"], 0) + 1
    ordered = sorted(counts.items(), key=lambda pair: pair[1], reverse=True)
    return ordered[:limit]


DEMO = [
    {"level": "INFO", "time": "09:12:01", "source": "api"},
    {"level": "WARN", "time": "09:12:04", "source": "db"},
    {"level": "ERROR", "time": "09:13:22", "source": "api"},
    {"level": "ERROR", "time": "10:01:00", "source": "db"},
    {"level": "INFO", "time": "10:02:11", "source": "api"},
]


if __name__ == "__main__":
    print("by level:", count_by_level(DEMO))
    print("by hour:", count_by_hour(DEMO))
    print(f"error ratio: {error_ratio(DEMO):.1%}")
    print("alert:", should_alert(DEMO))
    print("top sources:", top_sources(DEMO))
