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

    return {
        "psv_points": psv["points"],
        "psv_played": psv["playedGames"],
        "second_name": second["team"]["name"],
        "second_points": second["points"],
        "second_played": second["playedGames"],
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
        fixtures.append({
            "date": datetime.fromisoformat(m["utcDate"].replace("Z", "")),
            "opponent": m["awayTeam"]["name"]
            if m["homeTeam"]["name"] == "PSV"
            else m["homeTeam"]["name"]
        })

    fixtures.sort(key=lambda x: x["date"])
    return fixtures


# ==== Kernlogica: kampioensberekening ====
def calculate_championship(psv_points, second_points, fixtures, psv_played, second_played):
    # Maximaal aantal punten nummer 2 kan nog behalen
    remaining_second = TOTAL_MATCHES - second_played
    max_second_points = second_points + remaining_second * 3

    # Punten die PSV nodig heeft om zeker kampioen te zijn
    points_needed_psv = max_second_points + 1
    points_to_win = points_needed_psv - psv_points

    if points_to_win <= 0:
        # PSV al kampioen
        return {
            "date": None,
            "opponent": None,
            "psv_points": psv_points,
            "max_second_points": max_second_points,
            "matches_after": TOTAL_MATCHES - psv_played
        }

    # Bepaal hoeveel wedstrijden PSV minimaal moet winnen
    matches_needed = (points_to_win + 2) // 3  # +2 voor afronding naar boven

    if matches_needed > len(fixtures):
        # PSV kan niet kampioen worden met de resterende wedstrijden (theoretisch)
        return None

    kampioenswedstrijd = fixtures[matches_needed - 1]

    matches_after = TOTAL_MATCHES - (psv_played + matches_needed)

    return {
        "date": kampioenswedstrijd["date"],
        "opponent": kampioenswedstrijd["opponent"],
        "psv_points": points_needed_psv,
        "max_second_points": max_second_points,
        "matches_after": matches_after,
    }


# ==== HTML renderen ====
def render(result, stand):
    with open("index.html", encoding="utf-8") as f:
        template = Template(f.read())

    psv_remaining_now = TOTAL_MATCHES - stand["psv_played"]
    second_remaining_now = TOTAL_MATCHES - stand["second_played"]
    points_gap_now = result["psv_points"] - result["max_second_points"] if result else 0

    html = template.render(
        date=result["date"].strftime("%A %d %B") if result else "Nog onbekend",
        opponent=result["opponent"] if result else "-",
        psv_points=result["psv_points"] if result else stand["psv_points"],
        max_second=result["max_second_points"] if result else stand["second_points"],
        second_name=stand["second_name"],
        points_gap=points_gap_now,
        matches_after=result["matches_after"] if result else "-",
        psv_played=stand["psv_played"],
        psv_remaining=psv_remaining_now,
        second_played=stand["second_played"],
        second_remaining=second_remaining_now,
        updated=datetime.now().strftime("%d-%m %H:%M"),
    )

    os.makedirs("docs", exist_ok=True)
    with open("docs/index.html", "w", encoding="utf-8") as f:
        f.write(html)


# ==== Main ====
if __name__ == "__main__":
    stand = get_standings()
    fixtures = get_psv_fixtures()

    result = calculate_championship(
        stand["psv_points"],
        stand["second_points"],
        fixtures,
        stand["psv_played"],
        stand["second_played"]
    )

    render(result, stand)

    if result:
        if result["date"]:
            print(
                f"PSV is kampioen vanaf {result['date'].strftime('%d-%m-%Y')} "
                f"tegen {result['opponent']} "
                f"({result['matches_after']} wedstrijden voor het einde)"
            )
        else:
            print("PSV is al kampioen!")
    else:
        print("PSV kan theoretisch nog ingehaald worden.")