# Holidays ICS Generator Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Python script that crawls timeanddate.com for international holidays, generates a `.ics` file, and auto-updates quarterly via GitHub Actions.

**Architecture:** Single Python script (`main.py`) with three modules — crawler (fetch pages), parser (extract holidays from HTML), generator (create ICS). GitHub Actions cron triggers the script quarterly. Atomic output via tmp file + rename.

**Tech Stack:** Python 3, requests, beautifulsoup4, ics, GitHub Actions

---

## File Map

| File | Responsibility |
|------|---------------|
| `main.py` | All logic: crawl → parse → generate ICS, with 3-retry wrapper |
| `requirements.txt` | Python dependencies |
| `.github/workflows/update.yml` | CI schedule trigger + manual dispatch |
| `.gitignore` | Exclude Python cache, venv |
| `holidays.ics` | Generated output (committed to repo, subscribed by users) |

---

### Task 1: Project scaffolding

**Files:**
- Create: `requirements.txt`
- Modify: `.gitignore`

- [ ] **Step 1: Write requirements.txt**

```
requests>=2.28
beautifulsoup4>=4.12
ics>=0.7
```

- [ ] **Step 2: Update .gitignore**

Append to existing `.gitignore`:

```
__pycache__/
*.pyc
.venv/
venv/
*.tmp
```

- [ ] **Step 3: Commit**

```bash
git add requirements.txt .gitignore
git commit -m "chore: add Python project scaffolding"
```

---

### Task 2: Research target URL and verify HTML structure

This task is about opening the target page in a browser to confirm the exact HTML structure before writing the parser. The target is timeanddate.com's international holidays / observances listing.

- [ ] **Step 1: Open target URL in browser**

Open `https://www.timeanddate.com/holidays/fun/` in a browser and inspect the HTML.

Look for:
- The table or list element that contains holiday entries
- The CSS class or tag structure of each row/entry
- How dates are formatted (e.g., `Jun 1`, `1 Jun`)
- How holiday names are nested (e.g., inside `<a>` tags)

- [ ] **Step 2: Note the year scope**

Check if the page shows holidays for the current year or a range. Note the URL pattern for year-specific pages if applicable.

- [ ] **Step 3: Document findings**

Note the exact CSS selectors needed. Expected structure (based on historical timeanddate.com patterns):

```html
<table class="zebra fw tb-wc">
  <tbody>
    <tr>
      <td>Jan 1</td>
      <td><a href="/holidays/fun/new-years-day/">New Year's Day</a></td>
    </tr>
    ...
  </tbody>
</table>
```

If the structure differs, note the actual selectors to use in Task 3.

---

### Task 3: Write main.py — crawler and parser

**Files:**
- Create: `main.py`

- [ ] **Step 1: Write the complete main.py**

```python
#!/usr/bin/env python3
"""Crawl timeanddate.com for international holidays and generate an .ics file."""

import os
import sys
import time
import re
from datetime import date, datetime, timedelta

import requests
from bs4 import BeautifulSoup
from ics import Calendar, Event

# --- Config ---
MAX_RETRIES = 3
RETRY_DELAY = 5  # seconds
USER_AGENT = "Mozilla/5.0 (compatible; HolidayCalendar/1.0; +https://github.com/tiraurum/Personalized-calendar)"
OUTPUT_FILE = "holidays.ics"
TMP_FILE = OUTPUT_FILE + ".tmp"

# Target: timeanddate.com fun holidays — monthly pages
BASE_URL = "https://www.timeanddate.com/holidays/fun/"
MONTHS = ["january", "february", "march", "april", "may", "june",
          "july", "august", "september", "october", "november", "december"]

# English → Chinese name mapping for common international holidays
# Any name not in this map will be included as-is (English)
NAME_MAP = {
    "New Year's Day": "新年",
    "Valentine's Day": "情人节",
    "International Women's Day": "国际妇女节",
    "April Fools' Day": "愚人节",
    "Earth Day": "世界地球日",
    "Mother's Day": "母亲节",
    "Father's Day": "父亲节",
    "Halloween": "万圣节",
    "Christmas Eve": "平安夜",
    "Christmas Day": "圣诞节",
    "New Year's Eve": "跨年夜",
    "Thanksgiving Day": "感恩节",
    "Easter Sunday": "复活节",
    "Easter Monday": "复活节星期一",
    "Good Friday": "耶稣受难日",
    "Saint Patrick's Day": "圣帕特里克节",
    "Cinco de Mayo": "五月五日节",
    "Boxing Day": "节礼日",
    "Labor Day": "劳动节",
    "Memorial Day": "阵亡将士纪念日",
    "Independence Day": "独立日",
    "Columbus Day": "哥伦布日",
    "Veterans Day": "退伍军人节",
    "Black Friday": "黑色星期五",
    "Cyber Monday": "网络星期一",
    "Hanukkah": "光明节",
    "Diwali": "排灯节",
    "Ramadan": "斋月",
    "Eid al-Fitr": "开斋节",
    "Eid al-Adha": "古尔邦节",
    "Chinese New Year": "春节",
    "Lunar New Year": "农历新年",
    "Lantern Festival": "元宵节",
    "Dragon Boat Festival": "端午节",
    "Mid-Autumn Festival": "中秋节",
    "Winter Solstice": "冬至",
    "Summer Solstice": "夏至",
    "Spring Equinox": "春分",
    "Autumnal Equinox": "秋分",
    "World Health Day": "世界卫生日",
    "World Environment Day": "世界环境日",
    "World Food Day": "世界粮食日",
    "Human Rights Day": "人权日",
    "International Youth Day": "国际青年日",
    "World Teachers' Day": "世界教师日",
    "Children's Day": "儿童节",
    "International Day of Peace": "国际和平日",
    "World Water Day": "世界水日",
    "International Literacy Day": "国际扫盲日",
    "World AIDS Day": "世界艾滋病日",
    "International Day of Persons with Disabilities": "国际残疾人日",
    "World Mental Health Day": "世界精神卫生日",
    "May Day": "五一劳动节",
    "International Workers' Day": "国际劳动节",
    "All Saints' Day": "万灵节",
    "All Souls' Day": "万灵节",
    "Ash Wednesday": "圣灰星期三",
    "Palm Sunday": "棕枝主日",
    "Corpus Christi": "基督圣体节",
    "Ascension Day": "耶稣升天节",
    "Assumption of Mary": "圣母升天节",
    "Immaculate Conception": "圣母无染原罪节",
    "Epiphany": "主显节",
    "Mardi Gras": "狂欢节",
    "Shrove Tuesday": "忏悔星期二",
    "Canada Day": "加拿大日",
    "Australia Day": "澳大利亚日",
    "Waitangi Day": "怀唐伊日",
    "Bastille Day": "法国国庆日",
    "St. Patrick's Day": "圣帕特里克节",
    "Mothering Sunday": "母亲节(英国)",
    "Father's Day": "父亲节",
}


# --- Crawler ---

def fetch_page(url):
    """Fetch a URL and return HTML text."""
    resp = requests.get(url, timeout=30, headers={"User-Agent": USER_AGENT})
    resp.raise_for_status()
    return resp.text


def crawl_all_months(year):
    """Crawl all 12 monthly fun-holiday pages for the given year.
    Returns a list of (date, name_en) tuples.
    """
    all_holidays = []
    for month_slug in MONTHS:
        url = f"{BASE_URL}{month_slug}/"
        try:
            html = fetch_page(url)
            holidays = parse_month_page(html, year)
            all_holidays.extend(holidays)
        except Exception as e:
            print(f"  Warning: failed to fetch {url}: {e}", file=sys.stderr)
            continue
    return all_holidays


# --- Parser ---

def parse_month_page(html, year):
    """Parse a monthly fun-holidays page and return list of (date, name_en)."""
    soup = BeautifulSoup(html, "html.parser")
    holidays = []

    # timeanddate.com uses tables with class containing 'zebra' for holiday listings
    table = soup.find("table", class_=re.compile("zebra"))
    if not table:
        table = soup.find("table", class_="fw")
    if not table:
        table = soup.find("table", class_=re.compile("tb-wc"))

    if not table:
        return holidays

    current_month_num = None
    for row in table.find_all("tr"):
        # Month separator row: look for <th> with month name
        th = row.find("th")
        if th:
            month_text = th.get_text(strip=True)
            current_month_num = parse_month_name(month_text)
            continue

        cells = row.find_all("td")
        if len(cells) < 2:
            continue

        # First cell: day number or "Mon DD" format
        date_text = cells[0].get_text(strip=True)
        # Second cell: holiday name (inside <a> tag)
        name_link = cells[1].find("a")
        if not name_link:
            continue
        name_en = name_link.get_text(strip=True)

        # Parse date
        parsed_date = parse_date_string(date_text, current_month_num, year)
        if parsed_date:
            holidays.append((parsed_date, name_en))

    return holidays


def parse_month_name(text):
    """Parse month name to 1-based month number."""
    month_names = {
        "january": 1, "february": 2, "march": 3, "april": 4,
        "may": 5, "june": 6, "july": 7, "august": 8,
        "september": 9, "october": 10, "november": 11, "december": 12,
    }
    text_lower = text.strip().lower()
    for name, num in month_names.items():
        if name in text_lower:
            return num
    return None


def parse_date_string(text, month_num, year):
    """Parse a date string like 'Jun 15' or '15' into a date object.
    month_num is used as fallback when the text only contains a day number.
    """
    text = text.strip()

    # Pattern: "Mon DD" or "Month DD" with year implied
    # e.g., "Jun 15", "15 Jun", "June 15"
    month_map = {
        "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
        "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
    }

    # Try "Mon DD" pattern
    for abbr, mn in month_map.items():
        if text.lower().startswith(abbr):
            rest = text[len(abbr):].strip()
            day = int(re.search(r"(\d+)", rest).group(1))
            return date(year, mn, day)

    # Try just a day number (rely on implicit month from page context)
    if text.isdigit():
        day = int(text)
        if month_num:
            return date(year, month_num, day)

    return None


# --- ICS Generator ---

def map_to_chinese(name_en):
    """Map English holiday name to Chinese. Falls back to English name if unknown."""
    # Normalize: strip extra whitespace, standardize apostrophes
    normalized = name_en.strip()
    # Try variations
    candidates = [
        normalized,
        normalized.replace("'", "'"),
        normalized.replace("'", "'"),
    ]
    for c in candidates:
        if c in NAME_MAP:
            return NAME_MAP[c]
    # Also try without trailing 's
    if normalized.endswith("s"):
        singular = normalized[:-1]
        if singular in NAME_MAP:
            return NAME_MAP[singular]
    return normalized


def generate_ics(holidays, output_path):
    """Generate a valid .ics file from a list of (date, name_en) tuples.
    Writes atomically via temp file.
    """
    cal = Calendar()
    cal.creator = "Personalized-calendar (github.com/tiraurum/Personalized-calendar)"

    # Deduplicate by date+name
    seen = set()
    for dt, name_en in sorted(holidays, key=lambda x: x[0]):
        key = (dt, name_en)
        if key in seen:
            continue
        seen.add(key)

        name_zh = map_to_chinese(name_en)

        event = Event()
        event.name = name_zh
        event.description = f"{name_zh}（{name_en}）"
        event.begin = dt
        event.end = dt  # Same day → all-day display
        event.make_all_day()
        cal.events.add(event)

    if len(cal.events) == 0:
        raise ValueError("No events generated — refusing to write empty calendar")

    # Atomic write: tmp first, then rename
    with open(output_path, "w", encoding="utf-8") as f:
        # ics library: use serialize() with proper CRLF line endings
        ics_text = cal.serialize()
        f.write(ics_text)

    print(f"  Generated {len(cal.events)} holiday events")


# --- Orchestrator ---

def main():
    """Run the full pipeline with retry logic."""
    today = date.today()
    # Generate for the next 12 months from today
    years_to_crawl = {today.year}
    end_date = today + timedelta(days=365)
    years_to_crawl.add(end_date.year)

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            print(f"Attempt {attempt}/{MAX_RETRIES}: Crawling holidays...")
            all_holidays = []

            for year in sorted(years_to_crawl):
                print(f"  Crawling year {year}...")
                holidays = crawl_all_months(year)
                all_holidays.extend(holidays)

            if not all_holidays:
                raise ValueError("No holidays parsed from any source — possible site structure change")

            generate_ics(all_holidays, TMP_FILE)

            # Verify the temp file exists and is non-empty
            if not os.path.exists(TMP_FILE) or os.path.getsize(TMP_FILE) == 0:
                raise RuntimeError("Generated ICS file is empty or missing")

            # Atomically replace
            os.replace(TMP_FILE, OUTPUT_FILE)
            print(f"Successfully generated {OUTPUT_FILE} with {len(all_holidays)} raw entries")
            return 0

        except Exception as e:
            print(f"Attempt {attempt}/{MAX_RETRIES} failed: {e}", file=sys.stderr)
            if attempt < MAX_RETRIES:
                print(f"  Retrying in {RETRY_DELAY}s...")
                time.sleep(RETRY_DELAY)
            else:
                print("All retries exhausted. Keeping existing holidays.ics unchanged.", file=sys.stderr)
                return 1


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: Verify the script parses correctly**

Run: `python -c "import ast; ast.parse(open('main.py').read()); print('Syntax OK')"`
Expected: `Syntax OK`

- [ ] **Step 3: Commit**

```bash
git add main.py
git commit -m "feat: add main.py — crawl, parse, and generate holidays.ics"
```

---

### Task 4: Write GitHub Actions workflow

**Files:**
- Create: `.github/workflows/update.yml`

- [ ] **Step 1: Write the workflow file**

```yaml
name: Update Holidays Calendar

on:
  schedule:
    # Quarterly: 1st day of Jan, Apr, Jul, Oct at 00:00 UTC
    - cron: '0 0 1 1,4,7,10 *'
  workflow_dispatch:

jobs:
  update:
    runs-on: ubuntu-latest
    permissions:
      contents: write

    steps:
      - name: Checkout repository
        uses: actions/checkout@v4

      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.12'

      - name: Install dependencies
        run: pip install -r requirements.txt

      - name: Run holiday scraper
        run: python main.py

      - name: Commit and push updated ICS
        run: |
          git config user.name "github-actions[bot]"
          git config user.email "github-actions[bot]@users.noreply.github.com"
          if [ -n "$(git status --porcelain holidays.ics)" ]; then
            git add holidays.ics
            git commit -m "chore: update holidays.ics [skip ci]"
            git push
          else
            echo "No changes to holidays.ics"
          fi
```

- [ ] **Step 2: Commit**

```bash
git add .github/workflows/update.yml
git commit -m "ci: add GitHub Actions workflow for quarterly holiday updates"
```

---

### Task 5: Run scraper for the first time and verify output

- [ ] **Step 1: Install dependencies**

```bash
pip install -r requirements.txt
```

- [ ] **Step 2: Run the scraper**

```bash
python main.py
```

Expected: Script runs, outputs success message with holiday count. File `holidays.ics` is created.

- [ ] **Step 3: Validate the ICS file**

```bash
python -c "
from ics import Calendar
with open('holidays.ics', 'r') as f:
    cal = Calendar(f.read())
print(f'Events: {len(cal.events)}')
for e in sorted(cal.events, key=lambda x: x.begin)[:5]:
    print(f'  {e.begin.date()} — {e.name}')
print('  ...')
"
```

Expected: Events listed with dates and Chinese names.

- [ ] **Step 4: Inspect output manually**

Open `holidays.ics` in a text editor and spot-check:
- `BEGIN:VCALENDAR` / `END:VCALENDAR` present
- Events have `DTSTART;VALUE=DATE:YYYYMMDD` format
- `SUMMARY` has Chinese names
- `DESCRIPTION` has bilingual content

- [ ] **Step 5: Commit**

```bash
git add holidays.ics
git commit -m "feat: initial holidays.ics with international holidays"
```

---

### Task 6: Push and subscribe in Apple Calendar

- [ ] **Step 1: Push to GitHub**

```bash
git push origin main
```

- [ ] **Step 2: Get the raw URL**

The subscription URL will be:
`https://raw.githubusercontent.com/tiraurum/Personalized-calendar/main/holidays.ics`

- [ ] **Step 3: Add to Apple Calendar**

1. Open Apple Calendar (macOS / iOS)
2. File → New Calendar Subscription...
3. Paste: `https://raw.githubusercontent.com/tiraurum/Personalized-calendar/main/holidays.ics`
4. Click Subscribe, set auto-refresh to weekly
5. Confirm holidays appear in the calendar

---

### Task 7: Test retry and error handling

- [ ] **Step 1: Simulate network failure**

Temporarily change `BASE_URL` in main.py to an invalid URL like `https://invalid.example.com/`, then run:

```bash
python main.py; echo "Exit code: $?"
```

Expected:
- Script retries 3 times with 5s delay
- Prints error messages for each attempt
- Exits with code 1
- Existing `holidays.ics` is NOT overwritten (verify with git diff)

- [ ] **Step 2: Restore correct URL and confirm recovery**

```bash
git checkout main.py
python main.py
```

Expected: Script succeeds, `holidays.ics` updated.

- [ ] **Step 3: Commit if any changes from testing**

```bash
# Clean up — no changes expected after checkout
git status
```
