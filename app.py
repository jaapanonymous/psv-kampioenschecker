from flask import Flask, send_from_directory
import footballdataorg  # jouw bestaande script

app = Flask(__name__)

@app.route("/")
def index():
    # genereer de laatste HTML
    stand = footballdataorg.get_standings()
    fixtures = footballdataorg.get_psv_fixtures()
    result = footballdataorg.calculate_championship(
        stand["psv_points"], stand["second_points"], fixtures
    )
    footballdataorg.render(result, stand["second_name"])
    return send_from_directory("dist", "index.html")

if __name__ == "__main__":
    app.run(debug=True)