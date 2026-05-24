#!/usr/bin/env python3
"""Generate an .ics file of international non-statutory holidays for Apple Calendar.

Uses deterministic date-calculation rules (no web scraping dependency).
Each holiday is defined by a rule: fixed date, Nth weekday of month, or
Easter-relative. The script computes dates for the next 12 months and writes
a valid ICS file atomically.
"""

import os
import sys
from calendar import monthrange
from datetime import date, timedelta

# No external dependencies needed for ICS generation — we write the format directly.

OUTPUT_FILE = "holidays.ics"
TMP_FILE = OUTPUT_FILE + ".tmp"

# ── Holiday Definitions ──────────────────────────────────────────────────────
# Each entry: (chinese_name, english_name, rule)
#
# Rule types:
#   ("fixed", month, day)               — same date every year
#   ("nth_weekday", month, n, weekday)  — n-th occurrence of weekday in month
#                                         n can be negative: -1 = last
#   ("easter", offset_days)             — Easter Sunday + offset_days
#   ("last_weekday", month, weekday)    — last occurrence of weekday in month

HOLIDAYS = [
    # ── Fixed-date international holidays ──
    ("元旦", "New Year's Day", ("fixed", 1, 1)),
    ("情人节", "Valentine's Day", ("fixed", 2, 14)),
    ("国际妇女节", "International Women's Day", ("fixed", 3, 8)),
    ("圆周率日", "Pi Day", ("fixed", 3, 14)),
    ("圣帕特里克节", "St. Patrick's Day", ("fixed", 3, 17)),
    ("愚人节", "April Fools' Day", ("fixed", 4, 1)),
    ("世界地球日", "Earth Day", ("fixed", 4, 22)),
    ("星球大战日", "Star Wars Day", ("fixed", 5, 4)),
    ("五月五日节", "Cinco de Mayo", ("fixed", 5, 5)),
    ("世界环境日", "World Environment Day", ("fixed", 6, 5)),
    ("国际青年日", "International Youth Day", ("fixed", 8, 12)),
    ("国际扫盲日", "International Literacy Day", ("fixed", 9, 8)),
    ("万圣节", "Halloween", ("fixed", 10, 31)),
    ("国际男人节", "International Men's Day", ("fixed", 11, 19)),
    ("世界厕所日", "World Toilet Day", ("fixed", 11, 19)),
    ("人权日", "Human Rights Day", ("fixed", 12, 10)),
    ("平安夜", "Christmas Eve", ("fixed", 12, 24)),
    ("圣诞节", "Christmas Day", ("fixed", 12, 25)),
    ("节礼日", "Boxing Day", ("fixed", 12, 26)),
    ("跨年夜", "New Year's Eve", ("fixed", 12, 31)),

    # ── Nth-weekday holidays ──
    # (month, n, weekday) — n=1..5 or -1 for last; weekday=0(Mon)..6(Sun)
    ("母亲节", "Mother's Day", ("nth_weekday", 5, 2, 6)),         # 2nd Sunday of May
    ("父亲节", "Father's Day", ("nth_weekday", 6, 3, 6)),         # 3rd Sunday of June
    ("感恩节", "Thanksgiving Day", ("nth_weekday", 11, 4, 3)),     # 4th Thursday of November
    ("黑色星期五", "Black Friday", ("nth_weekday", 11, 4, 4)),     # Day after Thanksgiving (Fri)
    ("网络星期一", "Cyber Monday", ("nth_weekday", 11, 4, 0)),     # Mon after Thanksgiving

    # ── Last-weekday holidays ──
    ("阵亡将士纪念日", "Memorial Day", ("last_weekday", 5, 0)),    # last Monday of May
    ("劳动节", "Labor Day", ("nth_weekday", 9, 1, 0)),             # 1st Monday of September
    ("哥伦布日", "Columbus Day", ("nth_weekday", 10, 2, 0)),       # 2nd Monday of October

    # ── Easter-relative holidays ──
    ("复活节", "Easter Sunday", ("easter", 0)),
    ("耶稣受难日", "Good Friday", ("easter", -2)),
    ("复活节星期一", "Easter Monday", ("easter", 1)),
    ("圣灰星期三", "Ash Wednesday", ("easter", -46)),
    ("棕枝主日", "Palm Sunday", ("easter", -7)),
    ("耶稣升天节", "Ascension Day", ("easter", 39)),
    ("基督圣体节", "Corpus Christi", ("easter", 60)),
    ("忏悔星期二", "Shrove Tuesday", ("easter", -47)),

    # ── UN / WHO international days (fixed) ──
    ("世界水日", "World Water Day", ("fixed", 3, 22)),
    ("世界卫生日", "World Health Day", ("fixed", 4, 7)),
    ("国际和平日", "International Day of Peace", ("fixed", 9, 21)),
    ("世界教师节", "World Teachers' Day", ("fixed", 10, 5)),
    ("世界粮食日", "World Food Day", ("fixed", 10, 16)),
    ("世界精神卫生日", "World Mental Health Day", ("fixed", 10, 10)),
    ("世界艾滋病日", "World AIDS Day", ("fixed", 12, 1)),
    ("国际残疾人日", "International Day of Persons with Disabilities", ("fixed", 12, 3)),

    # ── Equinoxes & Solstices (astronomical, approximate) ──
    ("春分", "Spring Equinox", ("fixed", 3, 20)),
    ("夏至", "Summer Solstice", ("fixed", 6, 21)),
    ("秋分", "Autumnal Equinox", ("fixed", 9, 23)),
    ("冬至", "Winter Solstice", ("fixed", 12, 21)),

    # ── Other popular observances ──
    ("土拨鼠日", "Groundhog Day", ("fixed", 2, 2)),
    ("主显节", "Epiphany", ("fixed", 1, 6)),
    ("狂欢节", "Mardi Gras", ("easter", -47)),  # Same as Shrove Tuesday, keep both
    ("加拿大日", "Canada Day", ("fixed", 7, 1)),
    ("法国国庆日", "Bastille Day", ("fixed", 7, 14)),
    ("澳大利亚日", "Australia Day", ("fixed", 1, 26)),
    ("独立日", "Independence Day", ("fixed", 7, 4)),
    ("退伍军人节", "Veterans Day", ("fixed", 11, 11)),
]

# ── Deduplicate by (date, chinese_name)
HOLIDAYS_DEDUPED = []
seen_names = set()
for zh, en, rule in HOLIDAYS:
    key = zh
    if key not in seen_names:
        seen_names.add(key)
        HOLIDAYS_DEDUPED.append((zh, en, rule))
HOLIDAYS = HOLIDAYS_DEDUPED


# ── Date Calculation ─────────────────────────────────────────────────────────

def easter_sunday(year):
    """Compute Easter Sunday using the Anonymous Gregorian algorithm."""
    a = year % 19
    b = year // 100
    c = year % 100
    d = b // 4
    e = b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i = c // 4
    k = c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month = (h + l - 7 * m + 114) // 31
    day = ((h + l - 7 * m + 114) % 31) + 1
    return date(year, month, day)


def resolve_date(rule, year):
    """Compute the `date` for a holiday rule in a given year."""
    rtype = rule[0]

    if rtype == "fixed":
        _, month, day = rule
        return date(year, month, day)

    if rtype in ("nth_weekday", "last_weekday"):
        _, month, n, weekday = rule
        # weekday: 0=Mon..6=Sun
        first_day = date(year, month, 1)
        first_weekday = first_day.weekday()  # 0=Mon..6=Sun
        days_until_target = (weekday - first_weekday) % 7
        first_occurrence = first_day + timedelta(days=days_until_target)

        if n > 0:
            target = first_occurrence + timedelta(weeks=n - 1)
        else:
            # n == -1: last occurrence
            _, last_day_of_month = monthrange(year, month)
            last_date = date(year, month, last_day_of_month)
            last_weekday_val = last_date.weekday()
            days_back = (last_weekday_val - weekday) % 7
            target = last_date - timedelta(days=days_back)

        return target

    if rtype == "easter":
        _, offset = rule
        return easter_sunday(year) + timedelta(days=offset)

    raise ValueError(f"Unknown rule type: {rtype}")


# ── ICS Generation ───────────────────────────────────────────────────────────

def generate_ics(entries, output_path):
    """Write an ICS file. `entries` is a list of (date, chinese_name, english_name)."""
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Personalized-calendar//github.com/tiraurum//EN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        "X-WR-CALNAME:国际节假日",
        "X-WR-CALDESC:非法定国际节假日补充日历",
        "X-WR-TIMEZONE:Asia/Shanghai",
    ]

    for dt, name_zh, name_en in entries:
        date_str = dt.strftime("%Y%m%d")
        # All-day events: DTEND is the day AFTER
        end_dt = dt + timedelta(days=1)
        end_str = end_dt.strftime("%Y%m%d")
        dtstamp = f"{date.today().strftime('%Y%m%d')}T000000Z"

        lines += [
            "BEGIN:VEVENT",
            f"DTSTART;VALUE=DATE:{date_str}",
            f"DTEND;VALUE=DATE:{end_str}",
            f"DTSTAMP:{dtstamp}",
            f"SUMMARY:{name_zh}",
            f"DESCRIPTION:{name_zh}（{name_en}）",
            "TRANSP:TRANSPARENT",
            "END:VEVENT",
        ]

    lines.append("END:VCALENDAR")

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\r\n".join(lines) + "\r\n")

    print(f"  Generated {len(entries)} holiday events")


# ── Orchestrator ─────────────────────────────────────────────────────────────

def main():
    today = date.today()
    end_date = today + timedelta(days=400)  # ~13 months to be safe

    entries = []
    current_year = today.year
    end_year = end_date.year

    for (name_zh, name_en, rule) in HOLIDAYS:
        for year in range(current_year, end_year + 1):
            try:
                dt = resolve_date(rule, year)
                if today <= dt <= end_date:
                    entries.append((dt, name_zh, name_en))
            except ValueError:
                # Some rules may not resolve for every year (edge cases)
                pass

    entries.sort(key=lambda x: x[0])

    if not entries:
        print("Error: no holidays generated", file=sys.stderr)
        return 1

    generate_ics(entries, TMP_FILE)

    if not os.path.exists(TMP_FILE) or os.path.getsize(TMP_FILE) == 0:
        print("Error: generated ICS file is empty", file=sys.stderr)
        return 1

    os.replace(TMP_FILE, OUTPUT_FILE)
    print(f"Successfully generated {OUTPUT_FILE} with {len(entries)} entries "
          f"({current_year}-{end_year})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
