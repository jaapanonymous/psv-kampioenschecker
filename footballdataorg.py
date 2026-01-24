import requests
from datetime import datetime
from jinja2 import Template
import os
import ssl
import warnings

# ==== SSL en warnings fix voor Windows ====
ssl._create_default_https_context = ssl._create_unverified_context
warnings.filterwarnings("ignore", message="Unverified HTTPS request")

# ==== API instellingen ====
API_KEY = "f79a7defb5d74795b3e267b69bc442b0"
HEADERS = {"X-Auth-Token": API_KEY}
COMPETITION_CODE = "DED"  # Eredivisie
PSV_ID = 674  # PSV team id in football-data.org

# ==== Functies ====
def get_standings():
    url = f"https://api.football-data.org/v4/competitions/{COMPETITION_CODE}/standings"
    resp = requests.get(url, headers=HEADERS, verify=False)
    print("Standings API status:", resp.status_code)
    print("Response text:", resp.text[:500])  # eerste 500 tekens

    if resp.status_code != 200:
        raise Exception(f"Fout bij ophalen standings: {resp.text}")

    data = resp.json()
    table = data["standings"][0]["table"]

    psv = next((team for team in table if team["team"]["id"] == PSV_ID), None)
    second = table[1] if table[0]["team"]["id"] == PSV_ID else table[0]

    if not psv or not second:
        raise Exception("Kan PSV of nummer 2 niet vinden in standings.")

    return {
        "psv_points": psv["points"],
        "second_name": second["team"]["name"],
        "second_points": second["points"],
    }

def get_psv_fixtures():
    url = "https://api.football-data.org/v4/teams/{}/matches".format(PSV_ID)
    resp = requests.get(
        url,
        headers=HEADERS,
        params={"status": "SCHEDULED", "competitions": COMPETITION_CODE},
        verify=False
    )
    print("Fixtures API status:", resp.status_code)
    print("Response text:", resp.text[:500])

    if resp.status_code != 200:
        raise Exception(f"Fout bij ophalen fixtures: {resp.text}")

    fixtures = []
    for f in resp.json()["matches"]:
        fixture_date = datetime.fromisoformat(f["utcDate"].replace("Z", ""))
        home = f["homeTeam"]["name"]
        away = f["awayTeam"]["name"]
        opponent = away if home == "PSV" else home
        fixtures.append({"date": fixture_date, "opponent": opponent})

    fixtures.sort(key=lambda x: x["date"])  # sorteer op datum
    return fixtures

def calculate_championship(psv_points, second_points, fixtures):
    """
    Bereken de eerste wedstrijd waarop PSV niet meer kan worden ingehaald.
    """
    remaining_matches = len(fixtures)
    current_gap = psv_points - second_points

    for i, match in enumerate(fixtures, start=1):
        max_second_remaining_points = (remaining_matches - i) * 3
        if current_gap > max_second_remaining_points:
            return {
                "date": match["date"],
                "opponent": match["opponent"],
                "psv_points": psv_points,
                "second_points_max": second_points + max_second_remaining_points,
            }
        # Simuleer PSV wint de wedstrijd (voor volgorde)
        psv_points += 3

    return None

def render(result, second_name):
    # Open template met utf-8 encoding
    with open("index.html", encoding="utf-8") as file:
        template = Template(file.read())

    html = template.render(
        date=result["date"].strftime("%A %d %B") if result else "Nog onbekend",
        opponent=result["opponent"] if result else "-",
        psv_points=result["psv_points"] if result else "-",
        max_second=result["second_points_max"] if result else "-",
        second_name=second_name,
        updated=datetime.now().strftime("%d-%m %H:%M"),
    )

    os.makedirs("docs", exist_ok=True)
    with open("docs/index.html", "w", encoding="utf-8") as f:
        f.write(html)
    print("HTML gegenereerd in docs/index.html")

# ==== Script uitvoering ====
if __name__ == "__main__":
    stand = get_standings()
    fixtures = get_psv_fixtures()
    result = calculate_championship(stand["psv_points"], stand["second_points"], fixtures)
    render(result, stand["second_name"])

    if result:
        print(f"PSV kan niet meer ingehaald worden vanaf {result['date'].strftime('%d-%m-%Y')} tegen {result['opponent']}")
    else:
        print("PSV kan theoretisch nog ingehaald worden tot het einde van het seizoen.")