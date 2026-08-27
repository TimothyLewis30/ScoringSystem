import os
from flask import Flask, render_template, request, redirect, url_for, session
from functools import cmp_to_key
import random

app = Flask(__name__)

# Mengambil SECRET_KEY dari Environment Variable di Render.
# Jika tidak ada di env (misal saat dijalankan lokal), akan membuat key acak secara otomatis.
app.secret_key = os.environ.get("SECRET_KEY", os.urandom(24).hex())

@app.route("/")
def index():
    group_teams = session.get("group_teams", [])
    group_matches = session.get("group_matches", [])
    
    standings = {team: 0 for team in group_teams}
    for match in group_matches:
        if match.get("winner"):
            standings[match["winner"]] += 1

    def compare_teams(team_a, team_b):
        if standings[team_a] != standings[team_b]:
            return standings[team_b] - standings[team_a]
            
        for match in group_matches:
            if match.get("winner"):
                if (match["team1"] == team_a and match["team2"] == team_b) or \
                   (match["team1"] == team_b and match["team2"] == team_a):
                    if match["winner"] == team_a:
                        return -1
                    elif match["winner"] == team_b:
                        return 1
        return 0

    sorted_teams = sorted(group_teams, key=cmp_to_key(compare_teams))
    group_standings = [(team, standings[team]) for team in sorted_teams]

    elim_rounds = session.get("elim_rounds", [])
    elim_champion = session.get("elim_champion", None)

    return render_template(
        "index.html",
        group_teams=group_teams,
        group_matches=group_matches,
        group_standings=group_standings,
        elim_rounds=elim_rounds,
        elim_champion=elim_champion
    )

@app.route("/group-stage", methods=["POST"])
def group_stage():
    teams = [t.strip() for t in request.form.getlist("teams") if t.strip()]
    
    if len(teams) < 2:
        return redirect(url_for("index"))

    matches = []
    match_id = 1
    for i in range(len(teams)):
        for j in range(i + 1, len(teams)):
            matches.append({
                "id": match_id,
                "team1": teams[i],
                "team2": teams[j],
                "winner": None
            })
            match_id += 1
            
    session["group_teams"] = teams
    session["group_matches"] = matches
    return redirect(url_for("index"))

@app.route("/group-stage/update", methods=["POST"])
def update_group_match():
    match_id = int(request.form.get("match_id"))
    winner = request.form.get("winner")
    
    matches = session.get("group_matches", [])
    for match in matches:
        if match["id"] == match_id:
            match["winner"] = winner
            break
            
    session["group_matches"] = matches
    return redirect(url_for("index"))

@app.route("/group-stage/reset")
def reset_group():
    session.pop("group_teams", None)
    session.pop("group_matches", None)
    return redirect(url_for("index"))

@app.route("/elimination", methods=["POST"])
def elimination():
    teams = [t.strip() for t in request.form.getlist("teams") if t.strip()]

    if len(teams) < 2:
        return redirect(url_for("index"))

    random.shuffle(teams)
    matches = []
    for i in range(0, len(teams), 2):
        if i + 1 < len(teams):
            matches.append({"team1": teams[i], "team2": teams[i+1], "winner": None})
        else:
            matches.append({"team1": teams[i], "team2": "BYE", "winner": teams[i]})

    session["elim_rounds"] = [matches]
    session["elim_champion"] = None
    return redirect(url_for("index"))

@app.route("/elimination/advance", methods=["POST"])
def advance_elimination():
    rounds = session.get("elim_rounds", [])
    if not rounds:
        return redirect(url_for("index"))

    current_round = rounds[-1]
    winners = []
    for i, match in enumerate(current_round):
        selected_winner = request.form.get(f"winner_{i}")
        winner_name = match["team2"] if match["team2"] == "BYE" else selected_winner
        match["winner"] = winner_name
        if winner_name:
            winners.append(winner_name)

    if len(winners) == len(current_round):
        if len(winners) == 1:
            session["elim_champion"] = winners[0]
        else:
            next_round = []
            for i in range(0, len(winners), 2):
                if i + 1 < len(winners):
                    next_round.append({"team1": winners[i], "team2": winners[i+1], "winner": None})
                else:
                    next_round.append({"team1": winners[i], "team2": "BYE", "winner": winners[i]})
            rounds.append(next_round)

    session["elim_rounds"] = rounds
    return redirect(url_for("index"))

@app.route("/elimination/reset")
def reset_elimination():
    session.pop("elim_rounds", None)
    session.pop("elim_champion", None)
    return redirect(url_for("index"))

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=True, host="0.0.0.0", port=port)