import os
import ssl
import warnings
import requests
from fastapi.responses import Response
from datetime import datetime
from fastapi import FastAPI, Request
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from dotenv import load_dotenv

# 1. Laad de variabelen uit het .env bestand
load_dotenv()

# ==== SSL fix voor lokale omgevingen ====
ssl._create_default_https_context = ssl._create_unverified_context
warnings.filterwarnings("ignore", message="Unverified HTTPS request")

app = FastAPI()
templates = Jinja2Templates(directory="templates")

# Dit zoekt de map 'templates' relatief aan het script zelf, 
# ongeacht vanuit welke map je de terminal runt.
current_dir = os.path.dirname(os.path.realpath(__file__))
templates = Jinja2Templates(directory=os.path.join(current_dir, "templates"))

# ==== Config ====
API_KEY = os.getenv("FOOTBALL_API_KEY")
HEADERS = {"X-Auth-Token": API_KEY}
COMPETITION_CODE = "DED"
PSV_ID = 674
TOTAL_MATCHES = 34

if not API_KEY:
    print("WAARSCHUWING: Geen FOOTBALL_API_KEY gevonden in de omgeving!")

def dutch_date(date_obj):
    """Vertaalt datum naar Nederlands."""
    if not date_obj: return "Nog onbekend"
    maanden = ["", "Januari", "Februari", "Maart", "April", "Mei", "Juni", "Juli", "Augustus", "September", "Oktober", "November", "December"]
    dagen = ["Maandag", "Dinsdag", "Woensdag", "Donderdag", "Vrijdag", "Zaterdag", "Zondag"]
    return f"{dagen[date_obj.weekday()]} {date_obj.day} {maanden[date_obj.month]}"

def get_standings():
    """Haalt de stand op en berekent de gecorrigeerde maximale punten."""
    url_standings = f"https://api.football-data.org/v4/competitions/{COMPETITION_CODE}/standings"
    r_s = requests.get(url_standings, headers=HEADERS, verify=False)
    data = r_s.json()
    
    if "standings" not in data:
        raise Exception(f"API Error: {data.get('message', 'Onbekende fout')}")

    table = data["standings"][0]["table"]
    
    # Haal resterende wedstrijden op voor onderlinge correctie
    url_matches = f"https://api.football-data.org/v4/teams/{PSV_ID}/matches?status=SCHEDULED"
    r_m = requests.get(url_matches, headers=HEADERS, verify=False)
    scheduled_matches = r_m.json().get("matches", [])
    
    teams_to_play_psv = [(m["awayTeam"]["id"] if m["homeTeam"]["id"] == PSV_ID else m["homeTeam"]["id"]) for m in scheduled_matches]
    
    psv = next(t for t in table if t["team"]["id"] == PSV_ID)
    competitors = [t for t in table if t["team"]["id"] != PSV_ID]
    
    # Bepaal nummer 2 op basis van verliespunten
    original_top_competitor = max(competitors, key=lambda t: (t["points"] + (TOTAL_MATCHES - t["playedGames"]) * 3))
    original_name = original_top_competitor["team"]["name"]

    top_5 = []
    for i in range(min(5, len(table))):
        team_data = table[i]
        top_5.append({
            "pos": team_data["position"],
            "name": team_data["team"]["shortName"],
            "played": team_data["playedGames"],
            "won": team_data["won"],
            "draw": team_data["draw"],
            "lost": team_data["lost"],
            "diff": team_data["goalDifference"],
            "points": team_data["points"]
        })

    for team in competitors:
        rem_games = TOTAL_MATCHES - team["playedGames"]
        theoretical_max = team["points"] + (rem_games * 3)
        team["corrected_max"] = theoretical_max - 3 if team["team"]["id"] in teams_to_play_psv else theoretical_max

    virtual_second = max(competitors, key=lambda t: t["corrected_max"])

    return {
        "psv_points": psv["points"],
        "psv_played": psv["playedGames"],
        "second_name": virtual_second["team"]["name"],
        "second_max_corrected": virtual_second["corrected_max"],
        "points_gap_now": psv["points"] - virtual_second["points"],
        "original_top_name": original_name,
        "is_switched": original_name != virtual_second["team"]["name"],
        "second_played": virtual_second["playedGames"],
        "top_5": top_5
    }

def get_psv_fixtures():
    """Haalt de komende wedstrijden van PSV op."""
    url = f"https://api.football-data.org/v4/teams/{PSV_ID}/matches"
    r = requests.get(url, headers=HEADERS, params={"status": "SCHEDULED", "competitions": COMPETITION_CODE}, verify=False)
    matches = r.json().get("matches", [])
    fixtures = []
    for m in matches:
        kickoff = datetime.fromisoformat(m["utcDate"].replace("Z", ""))
        opponent = m["awayTeam"]["name"] if m["homeTeam"]["id"] == PSV_ID else m["homeTeam"]["name"]
        fixtures.append({"kickoff": kickoff, "opponent": opponent})
    fixtures.sort(key=lambda x: x["kickoff"])
    return fixtures

def calculate_championship(psv_points, second_max_corrected, fixtures, psv_played):
    if psv_points > second_max_corrected: return "ALREADY_CHAMPION"
    points_needed = second_max_corrected + 1
    points_to_win = points_needed - psv_points
    matches_needed = (points_to_win + 2) // 3
    if matches_needed > len(fixtures): return None
    match = fixtures[matches_needed - 1]
    return {
        "kickoff": match["kickoff"],
        "opponent": match["opponent"],
        "psv_points_target": points_needed,
        "psv_points_after_wins": psv_points + (matches_needed * 3),
        "max_second_points": second_max_corrected,
        "matches_after": TOTAL_MATCHES - (psv_played + matches_needed),
        "aantal_wedstrijden": matches_needed
    }

@app.get("/", response_class=HTMLResponse)
async def homepage(request: Request):
    stand = get_standings()
    fixtures = get_psv_fixtures()
    result = calculate_championship(stand["psv_points"], stand["second_max_corrected"], fixtures, stand["psv_played"])
    
    is_champion = (result == "ALREADY_CHAMPION")
    display_date = "Kampioen!" if is_champion else (dutch_date(result["kickoff"]) if result else "Nog onbekend")

    context = {
        "request": request,
        "is_champion": is_champion,
        "date": display_date,
        "kickoff_iso": result["kickoff"].strftime("%Y-%m-%dT%H:%M:%S") if (not is_champion and result) else "",
        "opponent": result["opponent"] if (not is_champion and result) else "-",
        "psv_points": stand["psv_points"],
        "psv_points_after_wins": result["psv_points_after_wins"] if (not is_champion and result) else stand["psv_points"],
        "max_second": stand["second_max_corrected"],
        "second_name": stand["second_name"],
        "original_top_name": stand["original_top_name"],
        "is_switched": stand["is_switched"],
        "points_gap_now": stand["points_gap_now"],
        "matches_after": result["matches_after"] if (not is_champion and result) else 0,
        "aantal_wedstrijden": result["aantal_wedstrijden"] if (not is_champion and result) else 0,
        "psv_played": stand["psv_played"],
        "second_played": stand["second_played"],
        "updated": datetime.now().strftime("%d-%m %H:%M"),
        "top_5": stand["top_5"]
    }
    return templates.TemplateResponse("index.html", context)

BASE_URL = "https://wanneerispsvkampioen.nl"  # <-- Pas dit aan!

@app.get("/sitemap.xml", include_in_schema=False)
async def sitemap():
    pages = [
        {
            "loc": f"{BASE_URL}/",
            "lastmod": datetime.now().date().isoformat(),
            "changefreq": "daily",
            "priority": "1.0"
        },
        # Later kun je hier meer pagina’s toevoegen
    ]

    xml = '<?xml version="1.0" encoding="UTF-8"?>\n'
    xml += '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'

    for page in pages:
        xml += "  <url>\n"
        xml += f"    <loc>{page['loc']}</loc>\n"
        xml += f"    <lastmod>{page['lastmod']}</lastmod>\n"
        xml += f"    <changefreq>{page['changefreq']}</changefreq>\n"
        xml += f"    <priority>{page['priority']}</priority>\n"
        xml += "  </url>\n"

    xml += "</urlset>"

    return Response(content=xml, media_type="application/xml")

@app.get("/robots.txt", include_in_schema=False)
async def robots():
    content = f"""
User-agent: *
Allow: /

Sitemap: {BASE_URL}/sitemap.xml
"""
    return Response(content=content, media_type="text/plain")


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)