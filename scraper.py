from playwright.sync_api import sync_playwright
import csv
import time
from pathlib import Path
from urllib.parse import urljoin, urlparse, parse_qs
import re
from datetime import date, datetime
import pandas as pd
import os

BASE_URL = "https://www.mshsaa.org"
SCHOOL_PAGE = "https://www.mshsaa.org/MySchool/Schedule.aspx?s={school_id}"

USER_AGENT = "HighSchoolSportsResearchBot/1.0 (contact: apsago@mail.missouri.edu)"

schools = [
    {"school_name": "Columbia Independent", "school_id": 566},
    {"school_name": "Christian Fellowship", "school_id": 1099},
    {"school_name": "Father Tolton", "school_id": 917},
    {"school_name": "Battle High School", "school_id": 953},
    {"school_name": "Rock Bridge High School", "school_id": 578},
    {"school_name": "Hickman High School", "school_id": 85},
    {"school_name": "Hallsville High School", "school_id": 311},
    {"school_name": "Centralia High School", "school_id": 53},
    {"school_name": "Southern Boone High School", "school_id": 2},
    {"school_name": "Glasgow High School", "school_id": 302},
    {"school_name": "Harrisburg High School", "school_id": 313},
    {"school_name": "Higbee High School", "school_id": 317},
    {"school_name": "Jefferson City High School", "school_id": 84},
    {"school_name": "Helias High School", "school_id": 522},
    {"school_name": "Capital City High School", "school_id": 1540},
    {"school_name": "Blair Oaks High School", "school_id": 217},
    {"school_name": "Fulton High School", "school_id": 80},
    {"school_name": "Boonville High School", "school_id": 16},
    {"school_name": "Mexico High School", "school_id": 128},
    {"school_name": "Moberly High School", "school_id": 132},
    {"school_name": "California High School", "school_id": 582},
    {"school_name": "Camdenton High School", "school_id": 26},
    {"school_name": "Eldon High School", "school_id": 278},
    {"school_name": "Fayette High School", "school_id": 294},
    {"school_name": "Marshall High School", "school_id": 360},
    {"school_name": "Missouri Military Academy", "school_id": 569},
    {"school_name": "North Callaway High School", "school_id": 139},
    {"school_name": "Russellville High School", "school_id": 430},
    {"school_name": "Salisbury High School", "school_id": 431},
    {"school_name": "Osage High School", "school_id": 152},
    {"school_name": "Smith-Cotton High School", "school_id": 194},
    {"school_name": "South Callaway High School", "school_id": 197},
    {"school_name": "Tipton High School", "school_id": 474},
    {"school_name": "Versailles High School", "school_id": 485},
]

REQUEST_DELAY = 2

OUTPUT_DIR = Path("output")
OUTPUT_DIR.mkdir(exist_ok=True)

OUTPUT_FILE = OUTPUT_DIR / "events.csv"

activity_record = {
    "school_id": None,
    "school_name": None,
    "activity_name": None,
    "alg": None,
    "activity_url": None,
    "season": None,
    "level": None
}
#event_records = []
#activity_records = []

#04182026: updated to add JH, 8th and 7th
#04152026: added to create levels_of_play column
LEVEL_MAP = {
    "1": "Varsity",
    "2": "Junior Varsity",
    "3": "Sophomore",
    "4": "Freshman",
    "7": "Junior High",
    "5": "8th Grade",
    "6": "7th Grade"
}


def visit_school(page, school):
    school_id = school["school_id"]
    school_name = school["school_name"]
    url = SCHOOL_PAGE.format(school_id=school_id)

    print(f"\nVisiting {school_name} ({school_id}): {url}")

    page.goto(url, wait_until="domcontentloaded",timeout=15000)

    print(f"Final URL: {page.url}")

    title = page.title()
    h1_text = page.locator("h1").first.inner_text().strip()

    print(f"Page title: {title}")
    print(f"School heading: {h1_text}")

def safe_attr(row, selector, attr_name):
    element = row.locator(selector)

    if element.count() == 0:
        return None

    try:
        value = element.first.get_attribute(attr_name)
        return value if value else None
    except Exception:
        return None
    
#04152026: separating times and scores 
def split_time_and_score(raw_value):
    if not raw_value:
        return None, None

    value = " ".join(raw_value.split()).strip()
    lower_value = value.lower()

    # Future event times
    if "am" in lower_value or "pm" in lower_value:
        return value, None

    # Placeholder
    if lower_value == "tbd":
        return value, None

    # Scores like 4 - 8 or 4 - 7 (8) or 0-2
    if re.search(r"\d+\s*-\s*\d+", value):
        return None, value

    return None, None

#04182026: no longer in use
#04152026: added to get correct level of play
#def get_current_level_of_play(page):
#    try:
#        current_tab = page.locator("#LevelsOfPlay li.level.current").first
#        text = " ".join(current_tab.inner_text().split()).strip()
#        return text if text else None
#    except Exception:
#        return None

def collect_activity_links(page, school):
    school_id = school["school_id"]
    school_name = school["school_name"]

    school_url = SCHOOL_PAGE.format(school_id=school_id)
    page.goto(school_url, wait_until="domcontentloaded",timeout=15000)

    anchors = page.locator("#Activities a").all()

    activities = []

    for anchor in anchors:
        href = anchor.get_attribute("href")
        if not href:
            continue

        full_url = urljoin(BASE_URL, href)

        # extract alg value from URL
        parsed = urlparse(full_url)
        alg = parse_qs(parsed.query).get("alg", [None])[0]

        season = anchor.get_attribute("data-season")
        level = anchor.get_attribute("data-level")

        activity_name = " ".join(anchor.inner_text().split())
        if not activity_name:
            activity_name = f"Unknown Activity {alg}"

        record = {
            "school_id": school_id,
            "school_name": school_name,
            "activity_name": activity_name,
            "alg": alg,
            "activity_url": full_url,
            "season": season,
            "level": level
        }

        activities.append(record)

    return activities

def safe_rendered_text(row, selector):
    cell = row.locator(selector)

    if cell.count() == 0:
        return None

    try:
        text = " ".join(cell.first.inner_text().split())
        return text if text else None
    except Exception:
        return None

def fetch_matchup_address(detail_page, matchup_link):
    if not matchup_link:
        return None

    try:
        detail_page.goto(matchup_link, wait_until="domcontentloaded", timeout=15000)

        # Tournament.aspx pages expose the location in this span
        location_span = detail_page.locator("#ctl00_contentMain_lblLocation")
        if location_span.count() > 0:
            text = " ".join(location_span.first.inner_text().split())
            if text:
                return text

        # Matchup.aspx pages instead render a "Location" heading followed
        # by address lines as sibling divs, with no id on the container
        location_block = detail_page.locator(
            "xpath=//h1[contains(@class,'fs_header') and normalize-space(text())='Location']/parent::div"
        )
        if location_block.count() > 0:
            lines = [line.strip() for line in location_block.first.inner_text().split("\n")]
            lines = [line for line in lines if line and line not in ("Location", "Directions")]
            if lines:
                return ", ".join(lines)

        return None
    except Exception:
        return None

def collect_events_from_activity(page, activity, detail_page):
    page.goto(activity["activity_url"], wait_until="domcontentloaded", timeout=15000)

    #04182026: no longer in use
    #04152026: added to correctly find level of play
    #current_level_of_play = get_current_level_of_play(page)

    rows = page.locator("table.schedule tbody tr").all()
    print(f"Found {len(rows)} rows")

    events = []

    for i, row in enumerate(rows, start=1):
        #04182026: updated level of play
        row_level = row.get_attribute("data-level")
        level_of_play = LEVEL_MAP.get(str(row_level), f"Unknown ({row_level})")
        date = safe_rendered_text(row, "td.gamedate")
        event_name = safe_rendered_text(row, "td[id$='tdOpponent'] a")
        #04152026: updated event_name to capture tournament names
        if not event_name:
            event_name = safe_rendered_text(row, "td[id$='tdOpponent']")
        #04152026: updated to separate score/event time
        raw_time_or_score = safe_rendered_text(row, "td[id*='dScoreTime']")
        event_time, score = split_time_and_score(raw_time_or_score)
        location = None
        matchup_link = safe_attr(row, "td[id$='tdMatchup'] a", "href")
        if matchup_link:
            matchup_link = urljoin(BASE_URL, matchup_link)
        row_class = row.get_attribute("class") or ""
        if "tournament" in row_class:
            location = "tournament"
        elif "home" in row_class:
            location = "home"
        elif "away" in row_class:
            location = "away"
        else:
            location = None

        # skip rows that are basically empty / structural
        if not any([date, event_name, event_time, location]):
            continue

        address = fetch_matchup_address(detail_page, matchup_link)

        event = {
            "school_id": activity["school_id"],
            "school_name": activity["school_name"],
            "activity_name": activity["activity_name"],
            "alg": activity["alg"],
            #04182026 updated level_of_play
            "level_of_play": level_of_play or LEVEL_MAP.get(str(activity["level"]), f"Unknown ({activity['level']})"),
            "event_date": date,
            "event_time": event_time,
            #04152026: updated to add score to data, change event_name column header
            "score": score,
            "event_name": event_name,
            "location": location,
            "source_activity_url": activity["activity_url"],
            "matchup_link": matchup_link,
            "address": address,
        }

        events.append(event)

    return events

def main():
    event_records = []
    activity_records = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)

        context = browser.new_context(
            user_agent=USER_AGENT
        )

        page = context.new_page()
        detail_page = context.new_page()

        for school in schools:
            try: 
                activities = collect_activity_links(page, school)

                print(f"\n{school['school_name']} activities:")

                for activity in activities:
                    print(f"Found {len(activities)} activities for {school['school_name']}")

                activity_records.extend(activities)

                for activity in activities:
                    try:
                        print(f"\nScraping events for {activity['school_name']} - {activity['activity_name']}")

                        events = collect_events_from_activity(page, activity, detail_page)

                        #04302026: skip the printing
                        #for event in events:
                            #print(f"Collected {len(events)} events for {activity['activity_name']}")

                        event_records.extend(events)


                    except Exception as e:
                        print(
                            f"Error on activity {activity['activity_name']} "
                            f"for {activity['school_name']} ({activity['school_id']}): {e}"
                        )
                time.sleep(REQUEST_DELAY)

            except Exception as e:
                print(f"Error on school {school['school_name']} ({school['school_id']}): {e}")

        #4302026 trying to add filters to shorten this thing
        df = pd.DataFrame(event_records)

        df["alg_clean"] = df["alg"].astype(str).str.strip()

        # Filter out Music, Scholar Bowl, etc.
        df = df[~df["alg_clean"].isin(["1", "2", "29"])]

        # KOMU generally covers varsity sports only
        df = df[df["level_of_play"] == "Varsity"]

        df = df.drop(columns=["alg_clean"])

        #Convert event_date to usable format
        def parse_date(date_str):
            if pd.isna(date_str):
                return pd.NaT

            # handle cases like "3/20-27" → take first date
            if '-' in date_str:
                date_str = date_str.split('-')[0]

            # remove weird arrow formatting
            date_str = date_str.replace('⤷', '').strip()

            try:
                return datetime.strptime(date_str, "%m/%d").replace(year=datetime.now().year)
            except:
                return pd.NaT

        df['parsed_date'] = df['event_date'].apply(parse_date)

        today = datetime.now()

        # end of next month
        start = today.replace(day=1)
        end = start + pd.DateOffset(months=2)

        # keep only events in range
        df = df[(df['parsed_date'] >= start) & (df['parsed_date'] < end)]

        df = df.sort_values(by=['parsed_date', 'school_name'])

        # drop helper column
        df = df.drop(columns=['parsed_date'])

        # convert back to dict for rest of your pipeline
        event_records = df.to_dict(orient='records')
        
        print(f"\nWriting {len(event_records)} events to CSV...")

        if event_records:
            with open(OUTPUT_FILE, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(
                    f,
                    fieldnames=event_records[0].keys(),
                    #04202026: added quoting to help zapier parsing
                    #tryingthisagain
                    quoting=csv.QUOTE_ALL
                )
                writer.writeheader()
                writer.writerows(event_records)

            print(f"CSV saved to {OUTPUT_FILE}")
            xlsx_dated = f"output/KOMU-SportsData-{date.today()}.xlsx"
            xlsx_latest = "output/latest.xlsx"

            df = pd.DataFrame(event_records)
            df.to_excel(xlsx_dated, index=False)
            df.to_excel(xlsx_latest, index=False)

            print(f"Excel saved to {xlsx_dated} and {xlsx_latest}")

            df.to_json(
                "output/events.json",
                orient="records",
                indent=2,
                date_format="iso"
            )

            print("JSON saved")

        else:
            print("No events found; CSV not written.")

        browser.close()


if __name__ == "__main__":
    main()