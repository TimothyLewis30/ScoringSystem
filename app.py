from datetime import datetime, timedelta
from flask import Flask, redirect, render_template, request, session, url_for
import random
import os

app = Flask(__name__)
app.secret_key = "supersecretkey"

# ---------------- 1. ROUTE UTAMA ----------------
@app.route("/")
def index():
    return render_template("index.html")


# ---------------- 2. LOGIC GROUP STAGE (ELIMINASI TANPA SKOR) ----------------
def make_simple_bracket(teams):
    """Membuat bagan eliminasi tanpa skor. 
    Jika jumlah tim ganjil, tim terakhir otomatis Bye (Lolos Otomatis).
    """
    random.shuffle(teams)
    bracket = []
    n = len(teams)

    has_bye = (n % 2 != 0)
    if has_bye:
        bye_team = teams[-1]
        playing_teams = teams[:-1]
    else:
        playing_teams = teams

    match_id = 1
    for i in range(0, len(playing_teams), 2):
        bracket.append({
            "id": match_id,
            "team1": playing_teams[i],
            "team2": playing_teams[i + 1],
            "winner": None
        })
        match_id += 1

    if has_bye:
        bracket.append({
            "id": match_id,
            "team1": bye_team,
            "team2": "Lolos Otomatis",
            "winner": bye_team  # Langsung lolos ke babak berikutnya
        })

    return bracket


@app.route("/group-stage", methods=["GET", "POST"])
def group_stage():
    if request.method == "POST":
        teams = [
            t.strip()
            for t in request.form.get("teams", "").split("\n")
            if t.strip()
        ]

        if len(teams) < 2:
            return render_template(
                "group_stage.html", error="Minimal masukkan 2 tim!"
            )

        session.update({
            "group_teams": teams,
            "group_rounds": [make_simple_bracket(teams)],
            "group_champion": None,
        })
        return redirect(url_for("group_stage"))

    return render_template(
        "group_stage.html",
        teams=session.get("group_teams", []),
        rounds=session.get("group_rounds", []),
        champion=session.get("group_champion"),
    )


@app.route("/group-stage/update", methods=["POST"])
def update_group_match():
    rounds = session.get("group_rounds", [])
    match_id = int(request.form.get("match_id", -1))
    winner = request.form.get("winner")

    if rounds:
        current_round = rounds[-1]
        for m in current_round:
            if m["id"] == match_id:
                m["winner"] = winner if winner != "" else None
                break

        # Jika seluruh pertandingan di babak saat ini sudah ada pemenangnya:
        if all(m["winner"] for m in current_round):
            winners = [m["winner"] for m in current_round]

            if len(winners) == 1:
                # Jika tersisa 1 pemenang, atur sebagai Juara
                session["group_champion"] = winners[0]
            else:
                # Jika masih ada beberapa pemenang, buat babak eliminasi baru
                rounds.append(make_simple_bracket(winners))

    session["group_rounds"] = rounds
    session.modified = True
    return redirect(url_for("group_stage"))


@app.route("/group-stage/reset")
def reset_group():
    for k in ["group_teams", "group_rounds", "group_champion"]:
        session.pop(k, None)
    return redirect(url_for("group_stage"))

@app.route("/group-stage/shuffle")
def shuffle_group():
    teams = session.get("group_teams", [])
    if teams:
        session.update({
            "group_rounds": [make_simple_bracket(teams)],
            "group_champion": None,
        })
        session.modified = True
    return redirect(url_for("group_stage"))

# ---------------- 3. LOGIC ELIMINASI (DENGAN SKOR) ----------------
def make_bracket(teams):
    random.shuffle(teams)
    bracket = []
    n = len(teams)

    has_bye = (n % 2 != 0)
    if has_bye:
        bye_team = teams[-1]
        playing_teams = teams[:-1]
    else:
        playing_teams = teams

    for i in range(0, len(playing_teams), 2):
        bracket.append({
            "team1": playing_teams[i],
            "team2": playing_teams[i + 1],
            "winner": None,
            "sets_won": {"team1": 0, "team2": 0},
            "set_details": []
        })

    if has_bye:
        bracket.append({
            "team1": bye_team,
            "team2": "Lolos Otomatis",
            "winner": bye_team,
            "sets_won": {"team1": 0, "team2": 0},
            "set_details": []
        })

    return bracket


@app.route("/elimination", methods=["GET", "POST"])
def elimination():
    if request.method == "POST":
        teams = [
            t.strip()
            for t in request.form.get("teams", "").split("\n")
            if t.strip()
        ]
        match_format = int(request.form.get("match_format", 3))

        if len(teams) < 2:
            return render_template(
                "elimination.html", error="Minimal masukkan 2 tim!"
            )

        session.update({
            "elim_raw": teams,
            "elim_fmt": match_format,
            "elim_rounds": [make_bracket(teams)],
            "elim_champion": None,
        })
        return redirect(url_for("elimination"))

    fmt = session.get("elim_fmt", 3)
    modal_sets = 1 if fmt == 21 else fmt

    return render_template(
        "elimination.html",
        rounds=session.get("elim_rounds", []),
        champion=session.get("elim_champion"),
        v_match_format_game=modal_sets,
        raw_match_format=fmt,
    )


@app.route("/elimination/shuffle")
def shuffle_elimination():
    if session.get("elim_raw"):
        session.update({
            "elim_rounds": [make_bracket(session["elim_raw"])],
            "elim_champion": None,
        })
        session.modified = True
    return redirect(url_for("elimination"))


@app.route("/elimination/advance", methods=["POST"])
def advance_elimination():
    rounds = session.get("elim_rounds", [])
    idx = int(request.form.get("match_idx", -1))
    fmt = session.get("elim_fmt", 3)

    total_sets_to_check = 1 if fmt == 21 else fmt
    target_score = 21 if fmt == 21 else 11

    if fmt == 21:
        winning_sets_required = 1
    elif fmt == 5:
        winning_sets_required = 3
    else:
        winning_sets_required = 2

    if rounds and 0 <= idx < len(rounds[-1]):
        m = rounds[-1][idx]
        t1_sets = 0
        t2_sets = 0
        set_details = []

        for i in range(1, total_sets_to_check + 1):
            s1 = int(request.form.get(f"set_{i}_t1") or 0)
            s2 = int(request.form.get(f"set_{i}_t2") or 0)

            if s1 > 0 or s2 > 0:
                set_details.append({"t1": s1, "t2": s2})

                if (s1 >= target_score or s2 >= target_score) and abs(s1 - s2) >= 2:
                    if s1 > s2:
                        t1_sets += 1
                    else:
                        t2_sets += 1

        m["set_details"] = set_details
        m["sets_won"] = {"team1": t1_sets, "team2": t2_sets}

        if t1_sets >= winning_sets_required:
            m["winner"] = m["team1"]
        elif t2_sets >= winning_sets_required:
            m["winner"] = m["team2"]
        else:
            m["winner"] = None

    if rounds and all(m["winner"] for m in rounds[-1]):
        winners = [m["winner"] for m in rounds[-1]]

        if len(winners) == 1:
            session["elim_champion"] = winners[0]
        else:
            rounds.append(make_bracket(winners))

    session["elim_rounds"] = rounds
    session.modified = True
    return redirect(url_for("elimination"))


@app.route("/elimination/reset")
def reset_elimination():
    for k in ["elim_raw", "elim_fmt", "elim_rounds", "elim_champion"]:
        session.pop(k, None)
    return redirect(url_for("elimination"))


# ---------------- 4. KEEP-ALIVE ENDPOINT (UNTUK RENDER) ----------------
@app.route("/ping", methods=["GET"])
def ping():
    """Endpoint ringan untuk di-hit berkala agar Render tidak sleep."""
    return {"status": "alive", "message": "Server is active!"}, 200

if __name__ == "__main__":
    app.run(debug=True)
