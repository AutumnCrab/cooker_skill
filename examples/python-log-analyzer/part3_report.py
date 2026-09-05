"""Part 3 - text report. Run: python part3_report.py"""

BAR_WIDTH = 30
BAR_CHAR = "#"
LEVEL_ORDER = ("FATAL", "ERROR", "WARN", "INFO", "DEBUG")


def make_bar(value, maximum, width=BAR_WIDTH):
    if maximum <= 0:
        return ""
    filled = int(round(value / maximum * width))
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
    mark = "[ALERT]" if alerting else "[ OK  ]"
    return f"{mark} error ratio {ratio:.1%}"


def build_report(level_counts, hour_counts, ratio, alerting):
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
    return "\n".join(sections)


if __name__ == "__main__":
    demo_levels = {"INFO": 2, "WARN": 1, "ERROR": 2}
    demo_hours = {9: 3, 10: 2}
    print(build_report(demo_levels, demo_hours, 0.4, True))
