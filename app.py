from datetime import datetime, timedelta
import random
from flask import Flask, redirect, render_template, request, session, url_for

app = Flask(__name__)
app.secret_key = "pingpong_tournament_secret_key"


# ---------------- 1. ROUTE UTAMA ----------------
@app.route("/")
def index():
  return render_template("index.html")


# ---------------- 2. LOGIC GROUP STAGE ----------------
def generate_group_schedule(teams, start_time_str="08:00"):
  # Buat semua pasangan match (Round Robin)
  pairings = [
      (teams[i], teams[j])
      for i in range(len(teams))
      for j in range(i + 1, len(teams))
  ]
  random.shuffle(pairings)

  # Penjadwalan: Maksimal 2 match per slot jam & cegah bentrok tim
  slots = []
  for match in pairings:
    t1, t2 = match
    placed = False
    for slot in slots:
      teams_in_slot = {m[0] for m in slot} | {m[1] for m in slot}
      # Cek jika slot belum penuh (<2 match) DAN tim belum bertanding di slot ini
      if len(slot) < 2 and t1 not in teams_in_slot and t2 not in teams_in_slot:
        slot.append(match)
        placed = True
        break
    if not placed:
      slots.append([match])

  # Generate jam pertandingan (durasi 30 menit per slot)
  start_dt = datetime.strptime(start_time_str, "%H:%M")
  matches = []
  match_id = 1

  for slot_idx, slot in enumerate(slots):
    match_start = start_dt + timedelta(minutes=30 * slot_idx)
    match_end = match_start + timedelta(minutes=30)
    time_slot = (
        f"{match_start.strftime('%H:%M')} - {match_end.strftime('%H:%M')}"
    )

    for t1, t2 in slot:
      matches.append({
          "id": match_id,
          "team1": t1,
          "team2": t2,
          "winner": None,
          "time_slot": time_slot,
      })
      match_id += 1

  return matches


@app.route("/group-stage", methods=["GET", "POST"])
def group_stage():
  if request.method == "POST":
    teams = [
        t.strip()
        for t in request.form.get("teams", "").split("\n")
        if t.strip()
    ]
    start_time = request.form.get("start_time", "08:00")

    if len(teams) < 2:
      return render_template(
          "group_stage.html", error="Minimal masukkan 2 tim!"
      )

    session.update({
        "group_teams": teams,
        "group_start_time": start_time,
        "group_matches": generate_group_schedule(teams, start_time),
    })
    return redirect(url_for("group_stage"))

  teams = session.get("group_teams", [])
  matches = session.get("group_matches", [])

  # Hitung Statistik Klasemen
  stats = {
      t: {"team": t, "played": 0, "won": 0, "lost": 0, "points": 0} for t in teams
  }
  for m in matches:
    if m["winner"]:
      w = m["winner"]
      l = m["team2"] if m["winner"] == m["team1"] else m["team1"]
      stats[w]["won"] += 1
      stats[w]["points"] += 1
      stats[l]["lost"] += 1
      stats[w]["played"] += 1
      stats[l]["played"] += 1

  standings = sorted(
      stats.values(), key=lambda x: (x["points"], x["won"]), reverse=True
  )
  return render_template(
      "group_stage.html", teams=teams, matches=matches, standings=standings
  )


@app.route("/group-stage/shuffle")
def shuffle_group_matches():
  teams = session.get("group_teams", [])
  start_time = session.get("group_start_time", "08:00")
  if teams:
    session["group_matches"] = generate_group_schedule(teams, start_time)
    session.modified = True
  return redirect(url_for("group_stage"))


@app.route("/group-stage/update", methods=["POST"])
def update_group_match():
  matches = session.get("group_matches", [])
  match_id = int(request.form.get("match_id"))
  winner = request.form.get("winner")

  for m in matches:
    if m["id"] == match_id:
      m["winner"] = winner if winner != "" else None
      break

  session["group_matches"] = matches
  session.modified = True
  return redirect(url_for("group_stage"))


@app.route("/group-stage/reset")
def reset_group():
  for k in ["group_teams", "group_matches", "group_start_time"]:
    session.pop(k, None)
  return redirect(url_for("group_stage"))


# ---------------- 3. LOGIC ELIMINASI ----------------
def make_bracket(teams):
  random.shuffle(teams)
  return [
      {
          "team1": teams[i],
          "team2": teams[i + 1] if i + 1 < len(teams) else "Lolos Otomatis",
          "winner": teams[i] if i + 1 >= len(teams) else None,
          "sets_won": {"team1": 0, "team2": 0},
          "set_details": [],  # Menyimpan detail skor per set misal [{'t1': 11, 't2': 9}]
      }
      for i in range(0, len(teams), 2)
  ]

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

  return render_template(
      "elimination.html",
      rounds=session.get("elim_rounds", []),
      champion=session.get("elim_champion"),
      match_format=session.get("elim_fmt", 3),
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

  if rounds and 0 <= idx < len(rounds[-1]):
    m = rounds[-1][idx]
    t1_sets = 0
    t2_sets = 0
    set_details = []

    for i in range(1, fmt + 1):
      s1 = int(request.form.get(f"set_{i}_t1") or 0)
      s2 = int(request.form.get(f"set_{i}_t2") or 0)

      # Catat detail skor jika set dimainkan
      if s1 > 0 or s2 > 0:
        set_details.append({"t1": s1, "t2": s2})

        # Aturan menang set pingpong (min 11 poin & selisih 2)
        if (s1 >= 11 or s2 >= 11) and abs(s1 - s2) >= 2:
          if s1 > s2:
            t1_sets += 1
          else:
            t2_sets += 1

    m["set_details"] = set_details
    m["sets_won"] = {"team1": t1_sets, "team2": t2_sets}
    m["winner"] = (
        m["team1"]
        if t1_sets > t2_sets
        else (m["team2"] if t2_sets > t1_sets else None)
    )

  # Cek jika seluruh match pada babak ini selesai, buat babak berikutnya
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


if __name__ == "__main__":
  app.run(debug=True)