#!/usr/bin/env python3
"""
Kronängs IF Calendar Scraper v6 - with weather forecast
"""
import requests
from bs4 import BeautifulSoup
import json
import os
import re
from datetime import date, datetime, timedelta
from pathlib import Path
from urllib.parse import urljoin

# Current SportAdmin calendar: contains both matches and training sessions.
CALENDAR_URL = "https://www.kronangsif.se/kalender/?ID=38276"
TEAM_CALENDAR_URL = "https://www.kronangsif.se/kalender/ajaxKalender.asp?ID={team_id}"
HOME_URL = "https://www.kronangsif.se/"
FOGIS_API_URL = "https://api-fogis-association.azure-api.net/club"
OUTPUT_FILE = Path(__file__).parent / "data" / "calendar.json"
FOGIS_CLUB_ID = 8688
FOGIS_TEAM_NAMES = {
    286936: "P2009-2010",
    200322: "P2011",
    239536: "P2012",
    87251: "P2013",
    185875: "P2014",
    353087: "P2015",
    372809: "P2016",
    353066: "F2008-2010",
    67275: "F2011-2012",
    63822: "Herrar",
    176076: "Damer",
}

# Borås coordinates (Kronäng area)
LAT, LON = 57.72, 12.94

# WMO Weather codes: https://open-meteo.com/en/docs
WMO_CODES = {
    0: ("☀️", "Klar himmel"),
    1: ("🌤️", "Mestadels klart"),
    2: ("⛅", "Delvis molnigt"),
    3: ("☁️", "Molnigt"),
    45: ("🌫️", "Dimma"),
    48: ("🌫️", "Dimma"),
    51: ("🌧️", "Dis"),
    53: ("🌧️", "Dis"),
    55: ("🌧️", "Dis"),
    56: ("🌧️", "Frysande dis"),
    57: ("🌧️", "Frysande dis"),
    61: ("🌧️", "Regn"),
    63: ("🌧️", "Regn"),
    65: ("🌧️", "Regn"),
    66: ("🌧️", "Frysande regn"),
    67: ("🌧️", "Frysande regn"),
    71: ("❄️", "Snö"),
    73: ("❄️", "Snö"),
    75: ("❄️", "Snö"),
    77: ("❄️", "Snöbyar"),
    80: ("🌦️", "Regnskurar"),
    81: ("🌦️", "Regnskurar"),
    82: ("🌦️", "Regnskurar"),
    85: ("🌨️", "Snöbyar"),
    86: ("🌨️", "Snöbyar"),
    95: ("⛈️", "Åska"),
    96: ("⛈️", "Åska med hagel"),
    99: ("⛈️", "Åska med hagel"),
}

def fetch_weather():
    """Fetch 7-day hourly weather forecast from Open-Meteo."""
    url = (f"https://api.open-meteo.com/v1/forecast"
           f"?latitude={LAT}&longitude={LON}"
           f"&hourly=weathercode,temperature_2m"
           f"&timezone=Europe/Stockholm"
           f"&forecast_days=7")
    resp = requests.get(url, timeout=15)
    resp.raise_for_status()
    data = resp.json()['hourly']

    # Build lookup: "YYYY-MM-DDTHH" -> (code, temp)
    forecast = {}
    for i, t in enumerate(data['time']):
        hour_key = t.replace(':00', '')  # "2026-03-12T14"
        forecast[hour_key] = {
            'code': data['weathercode'][i],
            'temp': data['temperature_2m'][i]
        }
    return forecast


def get_weather_info(forecast, date_str, time_str):
    """Get weather for a specific date/time - falls back to nearest hour if exact not found."""
    if not date_str or not time_str:
        return None

    # Extract hour from time like "08:45" -> 8
    hour = int(time_str.split(':')[0])
    
    # Try exact match first
    hour_key = f"{date_str}T{hour:02d}"
    if hour_key in forecast:
        w = forecast[hour_key]
        icon, desc = WMO_CODES.get(w['code'], ("❓", "Okänt"))
        return {'icon': icon, 'desc': desc, 'temp': w['temp']}
    
    # Try to find nearest hour in forecast for this date
    date_key = f"{date_str}T"
    for h in range(24):
        check_key = f"{date_key}{h:02d}"
        if check_key in forecast:
            w = forecast[check_key]
            icon, desc = WMO_CODES.get(w['code'], ("❓", "Okänt"))
            return {'icon': icon, 'desc': desc, 'temp': w['temp']}
    
    return None


TEAM_IDS = {
    "38937": "Herr", "52695": "Dam", "38381": "Utvecklingslag",
    "224798": "P2009-2010", "260562": "P2011", "281528": "P2012",
    "324307": "P2013", "324331": "P2014", "56158": "P 2015",
    "414417": "P2016", "320864": "F2008-2010", "281521": "F2011-2012",
    "374981": "F2013/2014", "520574": "F2015-2016",
    "481208": "Fotbollsskolan födda 2017", "520555": "Fotbollsskolan födda 2018",
    "584817": "Fotbollsskolan födda 2020", "181941": "Klubbstuga",
    "430796": "VEO kamera",
}

ACTIVITY_TYPES = {
    "calBox1": "Träning", "calBox2": "Match", "calBox3": "Övrigt"
}

LOCKEROOM_PATTERN = re.compile(r"\(\s*(H\d+)\s*(B\d+)\s*\)\s*$", re.IGNORECASE)

SWEDISH_MONTHS = {
    "JANUARI": 1, "FEBRUARI": 2, "MARS": 3, "APRIL": 4,
    "MAJ": 5, "JUNI": 6, "JULI": 7, "AUGUSTI": 8,
    "SEPTEMBER": 9, "OKTOBER": 10, "NOVEMBER": 11, "DECEMBER": 12,
}


def fetch_calendar():
    headers = {"User-Agent": "Mozilla/5.0"}
    response = requests.get(CALENDAR_URL, headers=headers, timeout=30)
    response.raise_for_status()
    response.encoding = 'iso-8859-1'
    return response.text


def get_fogis_api_key():
    """Read the Fogis key from Actions or the ignored local development file."""
    api_key = os.environ.get("FOGIS_API_KEY", "").strip()
    if api_key:
        return api_key

    local_key_file = Path(__file__).parent / "Svff.token"
    if local_key_file.exists():
        return local_key_file.read_text(encoding="utf-8").strip()
    return ""


def fetch_fogis_games(api_key, from_date, to_date):
    """Fetch official club games from Fogis for an inclusive date range."""
    response = requests.get(
        f"{FOGIS_API_URL}/upcoming-games",
        params={
            "from": from_date.isoformat(),
            "to": to_date.isoformat(),
            "w": 3,
            "take": 1000,
            "includeCanceled": "false",
        },
        headers={"ApiKey": api_key, "Accept": "application/json"},
        timeout=30,
    )
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload.get("games"), list):
        raise ValueError("Fogis-svaret saknar games-listan")
    return payload["games"]


def build_standings(games):
    """Build Herrar and Damer tables from completed Fogis results."""
    target_teams = {63822: "Herrar", 176076: "Damer"}
    tables = {label: {} for label in target_teams.values()}

    competitions = {label: {} for label in target_teams.values()}
    for game in games:
        if not game.get("isFinished") or game.get("isCanceled") or game.get("isAbandoned"):
            continue
        for target_id, label in target_teams.items():
            if target_id in (game.get("homeTeamId"), game.get("awayTeamId")):
                key = (game.get("competitionId"), game.get("competitionName") or "Okänd tävling")
                competitions[label][key] = competitions[label].get(key, 0) + 1

    selected_competitions = {}
    for label, counts in competitions.items():
        if counts:
            selected = max(counts, key=counts.get)
            selected_competitions[label] = selected[0]
            print(f"{label} standings competition: {selected[0]} {selected[1]} ({counts[selected]} games)")

    for game in games:
        if not game.get("isFinished") or game.get("isCanceled") or game.get("isAbandoned"):
            continue
        home_id = game.get("homeTeamId")
        away_id = game.get("awayTeamId")
        home_score = game.get("goalsScoredHomeTeam")
        away_score = game.get("goalsScoredAwayTeam")
        if home_score is None or away_score is None:
            continue
        try:
            home_score, away_score = int(home_score), int(away_score)
        except (TypeError, ValueError):
            continue

        for target_id, label in target_teams.items():
            if target_id not in (home_id, away_id):
                continue
            if game.get("competitionId") != selected_competitions.get(label):
                continue
            table = tables[label]
            for side, team_id, team_name, score, opponent_score in (
                ("home", home_id, game.get("homeTeamName"), home_score, away_score),
                ("away", away_id, game.get("awayTeamName"), away_score, home_score),
            ):
                row = table.setdefault(str(team_id), {
                    "team_id": team_id,
                    "name": str(team_name or "Okänt lag").strip(),
                    "logo": game.get("homeTeamImageUrl") if side == "home" else game.get("awayTeamImageUrl"),
                    "played": 0,
                    "wins": 0,
                    "draws": 0,
                    "losses": 0,
                    "goals_for": 0,
                    "goals_against": 0,
                    "points": 0,
                })
                row["played"] += 1
                row["goals_for"] += score
                row["goals_against"] += opponent_score
                if score > opponent_score:
                    row["wins"] += 1
                    row["points"] += 3
                elif score == opponent_score:
                    row["draws"] += 1
                    row["points"] += 1
                else:
                    row["losses"] += 1

    return [
        {
            "key": key.lower(),
            "label": key,
            "rows": sorted(
                rows.values(),
                key=lambda row: (-row["points"], -row["wins"],
                                 -(row["goals_for"] - row["goals_against"]), row["name"]),
            ),
        }
        for key, rows in tables.items()
    ]


def normalize_fogis_team_name(name, team_id=None):
    """Keep the existing dashboard's compact team naming where possible."""
    if team_id in FOGIS_TEAM_NAMES:
        return FOGIS_TEAM_NAMES[team_id]
    cleaned = re.sub(r"\s+", " ", (name or "")).strip()
    if re.search(r"P\s*09/10", cleaned, re.IGNORECASE):
        return "P2009-2010"
    return cleaned or "Okänt lag"


def parse_fogis_games(games):
    """Convert Fogis games to the activity shape used by the dashboard."""
    activities = []
    for game in games:
        timestamp = str(game.get("timeAsDateTime") or "").strip()
        match = re.match(r"^(\d{4}-\d{2}-\d{2})T(\d{1,2}):(\d{2})", timestamp)
        if not match:
            continue

        match_date, hour, minute = match.groups()
        home_team_id = game.get("homeTeamId")
        away_team_id = game.get("awayTeamId")
        home_team = normalize_fogis_team_name(game.get("homeTeamName"), home_team_id)
        away_team = str(game.get("awayTeamName") or "Motståndarlaget").strip()
        is_home = game.get("homeClubId") == FOGIS_CLUB_ID
        own_team = home_team if is_home else normalize_fogis_team_name(away_team, away_team_id)
        opponent = away_team if is_home else home_team
        venue = re.sub(r"\s+", " ", str(game.get("venueName") or "")).strip()
        surface = str(game.get("venueSurfaceName") or "").strip()
        location = " ".join(part for part in (venue, surface) if part)
        referee_data = game.get("referees") or {}
        referee_names = []
        for field in (
            "name", "secondRefereeName", "assistant1Name", "assistant2Name",
            "fourthName", "extra1Name", "extra2Name", "observerName",
        ):
            referee_name = str(referee_data.get(field) or "").strip()
            if referee_name and referee_name not in referee_names:
                referee_names.append(referee_name)

        activities.append({
            "date": match_date,
            "day": match_date[8:10],
            "weekday": "",
            "time": f"{int(hour):02d}:{minute}",
            "end_time": "",
            "team": own_team,
            "team_id": str(home_team_id if is_home else away_team_id or ""),
            "type": "Match",
            "description": f"{opponent} {'hemma' if is_home else 'borta'}",
            "venue": venue,
            "calendar_venue": "",
            "location": location,
            "lockerooms": None,
            "home_logo_url": game.get("homeTeamImageUrl") or game.get("homeTeamImageSmlUrl") or "",
            "away_logo_url": game.get("awayTeamImageUrl") or game.get("awayTeamImageSmlUrl") or "",
            "referees": referee_names,
            "fogis_game_id": game.get("gameId"),
            "fogis_status": {
                "postponed": bool(game.get("isPostponed")),
                "abandoned": bool(game.get("isAbandoned")),
                "canceled": bool(game.get("isCanceled")),
                "finished": bool(game.get("isFinished")),
            },
        })
    return activities


def fetch_team_calendar(team_id):
    """Fetch a team's calendar, which contains training sessions as well as matches."""
    headers = {"User-Agent": "Mozilla/5.0"}
    response = requests.get(
        TEAM_CALENDAR_URL.format(team_id=team_id),
        headers=headers,
        timeout=30,
    )
    response.raise_for_status()
    response.encoding = 'iso-8859-1'
    return response.text


def fetch_homepage():
    headers = {"User-Agent": "Mozilla/5.0"}
    response = requests.get(HOME_URL, headers=headers, timeout=30)
    response.raise_for_status()
    response.encoding = 'iso-8859-1'
    return response.text


def parse_month_year(soup):
    """Extract month and year from the calendar header (e.g. 'MARS 2026')."""
    header = soup.find('b', style=re.compile(r'font-size'))
    if header:
        parts = header.get_text(strip=True).upper().split()
        if len(parts) == 2:
            month = SWEDISH_MONTHS.get(parts[0], datetime.now().month)
            year = int(parts[1]) if parts[1].isdigit() else datetime.now().year
            return month, year
    return datetime.now().month, datetime.now().year


def parse_calendar(html):
    soup = BeautifulSoup(html, 'html.parser')
    activities = []
    month_sections = []

    for header in soup.find_all('b', style=re.compile(r'font-size')):
        parts = header.get_text(strip=True).upper().split()
        if len(parts) != 2 or parts[0] not in SWEDISH_MONTHS or not parts[1].isdigit():
            continue
        label = header.find_parent('div', class_='inner')
        if label:
            month_sections.append((label, SWEDISH_MONTHS[parts[0]], int(parts[1])))

    if not month_sections:
        month, year = parse_month_year(soup)
        month_sections = [(soup, month, year)]

    def parse_day_rows(day_rows, month, year):
        for day_row in day_rows:
            # HTML has unclosed <td> tags — BS4 nests them.
            tds = day_row.find_all('td', recursive=False)
            day_num = ""
            weekday = ""

            for td in tds:
                if 'padding-left' in td.get('style', ''):
                    b = td.find('b')
                    if b:
                        day_num = b.text.strip()
                    font = td.find('font')
                    if font:
                        wday = font.get_text(strip=True)
                        if wday and len(wday) <= 4 and wday.isalpha():
                            weekday = wday

            if not day_num:
                continue

            try:
                iso_date = date(year, month, int(day_num)).isoformat()
            except ValueError:
                iso_date = ""

            inner_table = day_row.find('table', {'border': '0', 'cellspacing': '0', 'cellpadding': '0'})
            if not inner_table:
                continue

            for act_row in inner_table.find_all('tr'):
                activity = parse_activity(act_row, day_num, weekday, iso_date)
                if activity:
                    activities.append(activity)

    for index, (label, month, year) in enumerate(month_sections):
        if label is soup:
            parse_day_rows(soup.find_all('tr', class_=['dag', 'son', 'idag', 'innanidag']), month, year)
            continue

        for sibling in label.find_next_siblings():
            if sibling.name == 'div' and 'inner' in (sibling.get('class') or []):
                break
            if sibling.name == 'table' and 'mCal' in (sibling.get('class') or []):
                parse_day_rows(sibling.find_all('tr', class_=['dag', 'son', 'idag', 'innanidag']), month, year)

    first_month, first_year = month_sections[0][1:]
    return first_month, first_year, activities


def parse_sportadmin_match_calendar(html):
    """Parse current SportAdmin calendar events, including training sessions."""
    soup = BeautifulSoup(html, 'html.parser')
    month_node = soup.select_one('.sa-matches__month')
    month_text = month_node.get_text(' ', strip=True) if month_node else ''
    month_match = re.search(r'([A-ZÅÄÖ]+)\s+(\d{4})', month_text, re.I)
    month_names = {
        'januari': 1, 'februari': 2, 'mars': 3, 'april': 4, 'maj': 5, 'juni': 6,
        'juli': 7, 'augusti': 8, 'september': 9, 'oktober': 10, 'november': 11, 'december': 12,
    }
    month = month_names.get(month_match.group(1).lower(), date.today().month) if month_match else date.today().month
    year = int(month_match.group(2)) if month_match else date.today().year
    team_labels = {
        'P 2015': 'P2015', 'Pojkar födda 2015': 'P2015', 'Pojkar födda 2014': 'P2014',
        'Pojkar födda 2013': 'P2013', 'Pojkar födda 2012': 'P2012',
        'Pojkar födda 2011': 'P2011', 'Pojkar födda 2009-10': 'P2009-2010',
        'Dam': 'Damer', 'Herr': 'Herrar',
    }
    activities = []

    # The current SportAdmin calendar uses date groups and event cards rather
    # than the old match-row markup. This contains both matches and training.
    date_groups = soup.select('.sa-calendar__date-group')
    if date_groups:
        for date_group in date_groups:
            day_node = date_group.select_one('.sa-calendar__date-number')
            if not day_node:
                continue
            try:
                iso_date = date(year, month, int(day_node.get_text(strip=True))).isoformat()
            except ValueError:
                continue

            for event in date_group.select('.sa-calendar__event'):
                start_node = event.select_one('.sa-calendar__time-start')
                end_node = event.select_one('.sa-calendar__time-end')
                labels = event.select('.sa-calendar__event-label')
                heading_node = event.select_one('.sa-calendar__event-heading')
                location_node = event.select_one('.sa-calendar__event-location')
                if not start_node or not labels or not heading_node:
                    continue

                team = team_labels.get(labels[0].get_text(' ', strip=True), labels[0].get_text(' ', strip=True))
                heading = heading_node.get_text(' ', strip=True)
                location = location_node.get_text(' ', strip=True).lstrip(',').strip() if location_node else ''
                event_link = event.select_one('.sa-calendar__event-link')
                is_match = 'sa-calendar__event--game' in (event.get('class') or [])
                description = heading
                if is_match:
                    description = heading

                activities.append({
                    'date': iso_date,
                    'time': start_node.get_text(strip=True),
                    'end_time': end_node.get_text(strip=True) if end_node else '',
                    'team': team,
                    'type': 'Match' if is_match else ('Träning' if 'träning' in heading.lower() else 'Övrigt'),
                    'description': description,
                    'location': location,
                    'lockerooms': None,
                    'team_id': re.search(r'[?&]ID=(\d+)', labels[0].get('href', '')).group(1)
                        if re.search(r'[?&]ID=(\d+)', labels[0].get('href', '')) else None,
                })
        return month, year, activities

    for row in soup.select('.sa-matches__row'):
        day_node = row.select_one('.sa-matches__day')
        time_node = row.select_one('.sa-matches__time')
        group_node = row.select_one('.sa-matches__group')
        team_nodes = row.select('.sa-matches__team')
        if not day_node or not time_node or not group_node or len(team_nodes) < 2:
            continue
        own_node = row.select_one('.sa-matches__team-name--own')
        names = [node.select_one('.sa-matches__team-name').get_text(' ', strip=True) for node in team_nodes]
        is_home = bool(own_node and own_node in team_nodes[0].select('.sa-matches__team-name'))
        opponent = names[1] if is_home else names[0]
        group_text = group_node.get_text(' ', strip=True).split(',', 1)[0].strip()
        place_node = group_node.select_one('.sa-matches__place')
        activities.append({
            'date': f'{year:04d}-{month:02d}-{int(day_node.get_text(strip=True)):02d}',
            'time': time_node.get_text(strip=True),
            'team': team_labels.get(group_text, group_text),
            'type': 'Match',
            'description': f'{opponent} {"hemma" if is_home else "borta"}',
            'location': place_node.get_text(' ', strip=True) if place_node else '',
            'lockerooms': None,
        })
    return month, year, activities


def parse_activity(row, day, weekday, iso_date):
    # Each activity row has 2 top-level cells:
    #   cells[0]: time + calBox (activity type)
    #   cells[1]: team link + description/location
    cells = row.find_all('td', recursive=False)
    if len(cells) < 2:
        return None

    # Time
    time_cell = cells[0]
    span = time_cell.find('span')
    time_text = span.get_text(strip=True) if span else time_cell.get_text(strip=True)
    time_matches = re.findall(r'(\d{1,2}:\d{2})', time_text)
    time_str = time_matches[0] if time_matches else ""
    end_time = time_matches[1] if len(time_matches) > 1 else ""

    # Activity type
    act_type = "Övrigt"
    calbox = time_cell.find('div', class_=re.compile(r'calBox[123]'))
    if calbox:
        for c in calbox.get('class', []):
            if c in ACTIVITY_TYPES:
                act_type = ACTIVITY_TYPES[c]
                break

    # Team
    content = cells[1]
    team = None
    team_id = None

    for link in content.find_all('a', href=re.compile(r'ID=')):
        href = link.get('href', '')
        match = re.search(r'ID=(\d+)', href)
        if match and match.group(1):
            team_id = match.group(1)
            team = TEAM_IDS.get(team_id, link.text.strip())
        else:
            team = link.text.strip()
        break

    if not team:
        return None

    # Description and location
    description = ""
    location = ""
    lockerooms = None
    kal_link = content.find('a', class_='kal')
    if kal_link:
        text = kal_link.get_text(strip=True)
        if text and text != '(..)':
            if ',' in text:
                parts = text.split(',', 1)
                description = parts[0].strip()
                location = parts[1].strip()
            else:
                description = text
    else:
        # The upcoming-match view uses a calendar URL without the `kal` class
        # and renders the fixture as "Kronängs IF - Opponent".
        match_link = content.find('a', href=re.compile(r'kalender/'))
        if match_link:
            text = match_link.get_text(" ", strip=True)
            teams = re.split(r'\s+[-–]\s+', text, maxsplit=1)
            if len(teams) == 2:
                home_team, away_team = (part.strip() for part in teams)
                if re.search(r'kronängs?\s+if', home_team, re.IGNORECASE):
                    description = f"{away_team} hemma"
                else:
                    description = f"{home_team} borta"

                content_text = content.get_text(" ", strip=True)
                if ',' in content_text:
                    location_text = content_text.split(',', 1)[1]
                    location = location_text.split(home_team, 1)[0].strip()

    if description:
        match = LOCKEROOM_PATTERN.search(description)
        if match:
            home_room = match.group(1).upper()
            away_room = match.group(2).upper()
            lockerooms = {
                "raw": f"{home_room}{away_room}",
                "home": home_room,
                "away": away_room,
            }
            description = LOCKEROOM_PATTERN.sub("", description).strip()

    if not location and description:
        if 'hemma' in description.lower():
            location = "Kronängs Arena"
        elif 'borta' in description.lower():
            m = re.search(r'borta[,\s]+(.+)', description, re.I)
            if m:
                location = m.group(1).strip()

    return {
        "date": iso_date,   # "YYYY-MM-DD" — used by JS for past/future check
        "day": day,
        "weekday": weekday,
        "time": time_str,
        "end_time": end_time,
        "team": team,
        "team_id": team_id,
        "type": act_type,
        "description": description,
        "location": location,
        "lockerooms": lockerooms,
    }


def parse_latest_news(html, limit=2):
    soup = BeautifulSoup(html, 'html.parser')
    news_items = []

    # Homepage top stories live in .span99 > .inner blocks.
    for item in soup.select("div.span99 div.inner"):
        title_link = item.select_one("section .rub a")
        if not title_link:
            continue

        title = title_link.get_text(" ", strip=True)
        href = title_link.get("href", "").strip()
        if not title or not href:
            continue

        date_node = item.find("span", string=re.compile(r"\d{4}-\d{2}-\d{2}"))
        published_at = date_node.get_text(" ", strip=True) if date_node else ""

        image_node = item.select_one(".imgDiv img")
        image_url = image_node.get("src", "").strip() if image_node else ""
        if image_url:
            image_url = urljoin(HOME_URL, image_url)

        summary = ""
        for block in item.find_all("div", style=re.compile(r"margin-top:5px")):
            text = block.get_text(" ", strip=True)
            if text:
                summary = re.sub(r"\s+", " ", text)
                break

        news_items.append({
            "title": title,
            "published_at": published_at,
            "url": urljoin(HOME_URL, href),
            "image": image_url,
            "summary": summary,
        })

        if len(news_items) >= limit:
            break

    return news_items


def save_data(activities, month, year, latest_news, sources=None, standings=None):
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    if standings is None:
        try:
            with open(OUTPUT_FILE, encoding="utf-8") as f:
                standings = json.load(f).get("standings", [])
        except (OSError, ValueError, TypeError):
            standings = []
    data = {
        "last_updated": datetime.now().isoformat(),
        "source": sources or [CALENDAR_URL, "team calendars"],
        "month": month,
        "year": year,
        "activity_count": len(activities),
        "activities": activities,
        "standings": standings,
        "latest_news": latest_news,
    }
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"Saved {len(activities)} activities")


def existing_activity_count():
    """Return the number of activities in the last published data file."""
    try:
        with open(OUTPUT_FILE, encoding="utf-8") as f:
            previous = json.load(f)
        return len(previous.get("activities") or [])
    except (OSError, ValueError, TypeError):
        return 0


def main():
    print("Fetching Kronängs IF calendar...")
    today = date.today()
    fogis_api_key = get_fogis_api_key()
    fogis_enabled = bool(fogis_api_key)
    sources = [CALENDAR_URL, "team calendars"]

    if fogis_enabled:
        try:
            fogis_from = today - timedelta(days=7)
            fogis_to = today + timedelta(days=120)
            fogis_games = fetch_fogis_games(fogis_api_key, fogis_from, fogis_to)
            activities = parse_fogis_games(fogis_games)
            month, year = today.month, today.year
            sources = [f"{FOGIS_API_URL}/upcoming-games", "team calendars"]
            print(f"Fogis games: {len(activities)}")
        except Exception as error:
            print(f"Warning: Fogis unavailable, falling back to website calendar: {error}")
            fogis_enabled = False

    if not fogis_enabled:
        html = fetch_calendar()
        month, year, activities = parse_calendar(html)
        print(f"Calendar month: {month}/{year}")

    existing = {
        (a.get('date'), a.get('time'), a.get('team'), a.get('description'), a.get('location'))
        for a in activities
    }

    # The current SportAdmin main calendar contains the new calendar links
    # (ID/AID) and may include the detailed pitch label, such as Plan A/B.
    # Use it to enrich the authoritative Fogis fixtures.
    if fogis_enabled:
        try:
            calendar_html = fetch_calendar()
            _, _, calendar_activities = parse_sportadmin_match_calendar(calendar_html)
            calendar_matches = [item for item in calendar_activities if item.get("type") == "Match"]
            calendar_trainings = [item for item in calendar_activities if item.get("type") != "Match"]
            print(f"SportAdmin calendar activities available: {len(calendar_activities)} "
                  f"({len(calendar_matches)} matches, {len(calendar_trainings)} training/other)")

            for activity in calendar_trainings:
                key = (
                    activity.get('date'), activity.get('time'), activity.get('team'),
                    activity.get('description'), activity.get('location')
                )
                if key not in existing:
                    activities.append(activity)
                    existing.add(key)

            for activity in calendar_matches:
                activity_team = re.sub(r"\s+", "", str(activity.get("team") or "")).lower()
                activity_description = re.sub(r"\s+", " ", str(activity.get("description") or "")).strip().lower()
                for fogis_activity in activities:
                    fogis_team = re.sub(r"\s+", "", str(fogis_activity.get("team") or "")).lower()
                    fogis_description = re.sub(r"\s+", " ", str(fogis_activity.get("description") or "")).strip().lower()
                    same_match = (
                        activity.get("date") == fogis_activity.get("date")
                        and activity.get("time") == fogis_activity.get("time")
                        and (
                            activity.get("team_id") == fogis_activity.get("team_id")
                            or (activity_team and activity_team == fogis_team)
                            or (activity_description and activity_description == fogis_description
                                and not re.search(r'veo', activity_team))
                        )
                    )
                    if same_match:
                        if activity.get("location"):
                            fogis_activity["calendar_venue"] = activity["location"]
                        if activity.get("lockerooms"):
                            fogis_activity["lockerooms"] = activity["lockerooms"]
                        break
        except Exception as error:
            print(f"Warning: Could not enrich Fogis games from SportAdmin calendar: {error}")

    # Keep the legacy team-calendar pass as a compatibility fallback while
    # SportAdmin's main calendar is migrated. New training is read above.
    team_calendar_count = 0
    for team_id, team_name in TEAM_IDS.items():
        if team_name == "VEO kamera":
            continue
        try:
            _, _, team_activities = parse_calendar(fetch_team_calendar(team_id))
            for activity in team_activities:
                if fogis_enabled and activity.get("type") == "Match":
                    # Fogis is authoritative for the fixture, while the team
                    # calendar may contain the more specific pitch label
                    # (for example Plan A or Plan B). Enrich the same Fogis
                    # match when date/time/team identify it unambiguously.
                    activity_team = re.sub(r"\s+", "", str(activity.get("team") or "")).lower()
                    activity_description = re.sub(r"\s+", " ", str(activity.get("description") or "")).strip().lower()
                    for fogis_activity in activities:
                        fogis_team = re.sub(r"\s+", "", str(fogis_activity.get("team") or "")).lower()
                        fogis_description = re.sub(r"\s+", " ", str(fogis_activity.get("description") or "")).strip().lower()
                        same_match = (
                            activity.get("date") == fogis_activity.get("date")
                            and activity.get("time") == fogis_activity.get("time")
                            and (
                                activity.get("team_id") == fogis_activity.get("team_id")
                                or (activity_team and activity_team == fogis_team)
                                or (activity_description and activity_description == fogis_description
                                    and not re.search(r'veo', activity_team))
                            )
                        )
                        if same_match:
                            if activity.get("location"):
                                fogis_activity["calendar_venue"] = activity["location"]
                            if activity.get("lockerooms"):
                                fogis_activity["lockerooms"] = activity["lockerooms"]
                            break
                    continue
                key = (
                    activity.get('date'), activity.get('time'), activity.get('team'),
                    activity.get('description'), activity.get('location')
                )
                if key not in existing:
                    activities.append(activity)
                    existing.add(key)
            team_calendar_count += 1
        except Exception as e:
            print(f"Warning: Could not fetch calendar for {team_name} ({team_id}): {e}")
    print(f"Team calendars added: {team_calendar_count}")

    print("Fetching latest homepage news...")
    latest_news = []
    try:
        homepage_html = fetch_homepage()
        latest_news = parse_latest_news(homepage_html, limit=2)
        print(f"News added: {len(latest_news)} items")
    except Exception as e:
        print(f"Warning: Could not fetch latest news: {e}")

    standings = None
    if fogis_enabled:
        try:
            season_games = fetch_fogis_games(
                fogis_api_key,
                date(today.year, 1, 1),
                date(today.year, 12, 31),
            )
            standings = build_standings(season_games)
            print("Standings built: " + ", ".join(
                f"{table['label']} {len(table['rows'])} teams" for table in standings
            ))
        except Exception as error:
            print(f"Warning: Could not build Fogis standings: {error}")

    print("Fetching weather forecast...")
    try:
        forecast = fetch_weather()
        # Add weather to each activity
        for a in activities:
            a['weather'] = get_weather_info(forecast, a.get('date'), a.get('time'))
        weather_count = sum(1 for a in activities if a.get('weather'))
        print(f"Weather added to {weather_count} activities")
    except Exception as e:
        print(f"Warning: Could not fetch weather: {e}")

    # A failed upstream response must never replace a known-good calendar with
    # an empty one. This is especially important when both Fogis and the
    # legacy SportAdmin calendar are temporarily unavailable.
    if not activities:
        previous_count = existing_activity_count()
        if previous_count:
            raise RuntimeError(
                f"Scrape returned 0 activities while published data contains "
                f"{previous_count}; refusing to overwrite calendar.json"
            )

    save_data(activities, month, year, latest_news, sources=sources, standings=standings)
    print(f"Done! Found {len(activities)} activities")

if __name__ == "__main__":
    main()
