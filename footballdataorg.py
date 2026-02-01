import requests
from datetime import datetime
from jinja2 import Template
import os
import ssl
import warnings

# ==== SSL fix (Windows) ====
ssl._create_default_https_context = ssl._create_unverified_context
warnings.filterwarnings("ignore", message="Unverified HTTPS request")

# ==== Config ====
API_KEY = "f79a7defb5d74795b3e267b69bc442b0"
HEADERS = {"X-Auth-Token": API_KEY}

COMPETITION_CODE = "DED"
PSV_ID = 674
TOTAL_MATCHES = 34

# ==== Standings ophalen ====
def get_standings():
    url = f"https://api.football-data.org/v4/competitions/{COMPETITION_CODE}/standings"
    r = requests.get(url, headers=HEADERS, verify=False)
    r.raise_for_status()

    table = r.json()["standings"][0]["table"]

    psv = next(t for t in table if t["team"]["id"] == PSV_ID)
    second = table[1] if table[0]["team"]["id"] == PSV_ID else table[0]

    points_gap_now = psv["points"] - second["points"]

    return {
        "psv_points": psv["points"],
        "psv_played": psv["playedGames"],
        "second_name": second["team"]["name"],
        "second_points": second["points"],
        "second_played": second["playedGames"],
        "points_gap_now": points_gap_now
    }

# ==== PSV fixtures ophalen ====
def get_psv_fixtures():
    url = f"https://api.football-data.org/v4/teams/{PSV_ID}/matches"
    r = requests.get(
        url,
        headers=HEADERS,
        params={"status": "SCHEDULED", "competitions": COMPETITION_CODE},
        verify=False
    )
    r.raise_for_status()

    fixtures = []
    for m in r.json()["matches"]:
        kickoff = datetime.fromisoformat(m["utcDate"].replace("Z", ""))
        opponent = (
            m["awayTeam"]["name"]
            if m["homeTeam"]["name"] == "PSV"
            else m["homeTeam"]["name"]
        )
        fixtures.append({
            "kickoff": kickoff,
            "opponent": opponent
        })
    fixtures.sort(key=lambda x: x["kickoff"])
    return fixtures

# ==== Kampioensberekening ====
def calculate_championship(psv_points, second_points, fixtures, psv_played, second_played):
    remaining_second = TOTAL_MATCHES - second_played
    max_second_points = second_points + remaining_second * 3

    points_needed_psv = max_second_points + 1
    points_to_win = points_needed_psv - psv_points

    if points_to_win <= 0:
        return {
            "kickoff": None,
            "opponent": None,
            "psv_points": psv_points,
            "max_second_points": max_second_points,
            "matches_after": TOTAL_MATCHES - psv_played,
        }

    matches_needed = (points_to_win + 2) // 3

    if matches_needed > len(fixtures):
        return None

    kampioenswedstrijd = fixtures[matches_needed - 1]
    matches_after = TOTAL_MATCHES - (psv_played + matches_needed)

    return {
        "kickoff": kampioenswedstrijd["kickoff"],
        "opponent": kampioenswedstrijd["opponent"],
        "psv_points": points_needed_psv,
        "max_second_points": max_second_points,
        "matches_after": matches_after,
    }

# ==== HTML renderen ====
def render(result, stand):
    with open("index.html", encoding="utf-8") as f:
        template = Template(f.read())

    html = template.render(
        date=(
            result["kickoff"].strftime("%A %d %B")
            if result and result["kickoff"]
            else "Nog onbekend"
        ),
        kickoff_iso=(
            result["kickoff"].strftime("%Y-%m-%dT%H:%M:%S")
            if result and result["kickoff"]
            else ""
        ),
        opponent=result["opponent"] if result else "-",
        psv_points=result["psv_points"] if result else stand["psv_points"],
        max_second=result["max_second_points"] if result else stand["second_points"],
        second_name=stand["second_name"],
        points_gap=(result["psv_points"] - result["max_second_points"] 
                    if result and result["kickoff"] 
                    else 0),
        points_gap_now=stand["points_gap_now"],
        matches_after=result["matches_after"] if result else "-",
        psv_played=stand["psv_played"],
        psv_remaining=TOTAL_MATCHES - stand["psv_played"],
        second_played=stand["second_played"],
        second_remaining=TOTAL_MATCHES - stand["second_played"],
        updated=datetime.now().strftime("%d-%m %H:%M"),
    )

    os.makedirs("docs", exist_ok=True)
    with open("docs/index.html", "w", encoding="utf-8") as f:
        f.write(html)

# ==== MAIN ====
if __name__ == "__main__":
    stand = get_standings()
    fixtures = get_psv_fixtures()

    result = calculate_championship(
        stand["psv_points"],
        stand["second_points"],
        fixtures,
        stand["psv_played"],
        stand["second_played"],
    )

    render(result, stand)

    if result:
        if result["kickoff"]:
            print(f"PSV kan kampioen worden op {result['kickoff'].strftime('%d-%m-%Y %H:%M')} tegen {result['opponent']}")
        else:
            print("PSV is al kampioen!")
    else:
        print("PSV kan theoretisch nog ingehaald worden.")