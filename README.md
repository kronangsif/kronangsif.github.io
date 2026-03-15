# Kronängs IF Dashboard

En statisk dashboard för Kronängs IF som hämtar klubbens kalenderdata, kompletterar utvalda aktiviteter med väderprognos och visar informationen i flera TV-vänliga vyer.

## Översikt

Projektet består av två huvuddelar:

- En Python-scraper som hämtar kalenderdata från Kronängs IF/SportAdmin och sparar den som JSON.
- En frontend i vanilla HTML/CSS/JS som visar datan i olika vyer, till exempel träningar, matcher samt separata dashboards för herr- och damlag.

Startsidan fungerar som en roterande dashboard där olika undersidor visas automatiskt enligt konfigurationen i `config.json`.

## Live

[https://fluxweaver.github.io/kronang-dashboard/](https://fluxweaver.github.io/kronang-dashboard/)

## Funktioner

- Hämtar kalenderaktiviteter från Kronängs IF:s kalenderkälla.
- Parsar aktiviteter till ett normaliserat JSON-format i `data/calendar.json`.
- Lägger till väderprognos för aktiviteter inom prognosfönstret.
- Visar filtrerade kalendervyer för träningar, matcher och specifika lag.
- Har en rotator för TV-skärm eller klubbdisplay som växlar mellan flera sidor automatiskt.
- Bäddar in serietabeller från Everysport för herr- och damvyer.
- Uppdaterar datan automatiskt via GitHub Actions varje timme.

## Projektstruktur

```text
kronang-dashboard/
├── index.html                 # Rotator/dashboard-shell
├── config.json                # Vilka sidor som visas och hur de roteras
├── calendar-embedded.html     # Generisk kalender-vy med URL-filter
├── training-embedded.html     # Träningsvy för idag/imorgon
├── matches-embedded.html      # Matchvy
├── herr-embedded.html         # Herrar-vy med tabell + matcher
├── dam-embedded.html          # Damer-vy med tabell + matcher
├── weather-embedded.html      # Separat vädervy
├── standings.html             # Enkel tabellvy
├── calendar.html              # Full kalenderdashboard
├── app.js                     # JavaScript för kalenderdashboarden
├── style.css                  # Gemensam styling
├── scraper.py                 # Hämtar och transformerar kalenderdata
├── requirements.txt           # Python-beroenden
├── data/
│   └── calendar.json          # Genererad kalenderdata
└── .github/workflows/
    └── scrape.yml             # Automatisk uppdatering via GitHub Actions
```

## Så fungerar det

### 1. Datainsamling

`scraper.py` hämtar kalender-HTML från Kronängs IF:s SportAdmin-källa, tolkar aktiviteterna och skriver resultatet till `data/calendar.json`.

JSON-filen innehåller bland annat:

- `last_updated`
- `month`
- `year`
- `activity_count`
- `activities`

Varje aktivitet innehåller fält som datum, tid, lag, aktivitetstyp, beskrivning, plats och eventuellt väder.

### 2. Presentation

Frontend-sidorna läser `data/calendar.json` direkt i webbläsaren.

- `calendar-embedded.html` är den centrala vykomponenten och kan filtreras via query-parametrar som `team`, `type` och `day`.
- `training-embedded.html` visar träningspass för idag och imorgon sida vid sida.
- `matches-embedded.html` visar kommande matcher.
- `herr-embedded.html` och `dam-embedded.html` kombinerar kalenderdata med inbäddade tabeller från Everysport.
- `index.html` laddar sidorna från `config.json` och roterar mellan dem automatiskt.

## Lokal körning

1. Klona repot:

```bash
git clone https://github.com/fluxweaver/kronang-dashboard.git
cd kronang-dashboard
```

2. Installera beroenden:

```bash
pip install -r requirements.txt
```

3. Kör scrapern för att generera aktuell data:

```bash
python scraper.py
```

4. Starta en enkel lokal webbserver:

```bash
python -m http.server 8000
```

5. Öppna dashboarden:

```text
http://localhost:8000/index.html
```

Du kan också öppna enskilda vyer direkt, till exempel `calendar-embedded.html` eller `training-embedded.html`.

## Deployment

Projektet är byggt för att fungera bra med GitHub Pages eftersom det är en statisk webbplats utan byggsteg.

1. Pusha repot till GitHub.
2. Aktivera GitHub Pages i repo-inställningarna.
3. Välj deployment från grenen `main`.
4. Publicera sidan på `https://<username>.github.io/kronang-dashboard/`.

## Automatisk uppdatering

GitHub Actions-workflowen i `.github/workflows/scrape.yml`:

- kör varje hel timme
- installerar Python-beroenden
- kör `scraper.py`
- committar och pushar ny data om `data/calendar.json` har ändrats

Manuell körning finns via GitHub Actions och `workflow_dispatch`.

## Tekniker

- Python 3.11
- Requests
- BeautifulSoup
- Vanilla HTML/CSS/JavaScript
- GitHub Actions
- GitHub Pages

## Datakällor

- [kronangsif.se](https://www.kronangsif.se) för kalenderdata
- [Open-Meteo](https://open-meteo.com/) för väderprognos
- [Everysport](https://www.everysport.com/) för inbäddade tabeller

## Licens

Ingen licensfil finns i repot just nu. Lägg till en `LICENSE` om projektet ska delas med en uttrycklig licens.
