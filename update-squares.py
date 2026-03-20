#!/usr/bin/env python3
"""
Fetches 2026 NCAA Tournament games from collegebasketballdata.com
and writes squares.json with winner/loser last-digit counts.
Runs via GitHub Actions every 30 minutes.
"""

import requests
import json
import os
from datetime import datetime, timezone
from collections import defaultdict

API_KEY  = os.environ.get("CBB_API_KEY", "")
BASE_URL = "https://api.collegebasketballdata.com/games"

HEADERS = {
    "Authorization": f"Bearer {API_KEY}",
    "Accept": "application/json"
}

# NCAA Tournament 2026: March–April 2026
DATE_CHUNKS = [
    ("2026-03-01T00:00:00Z", "2026-04-30T23:59:59Z"),
]

def fetch_tournament_games():
    all_games = []
    seen = set()

    for start, end in DATE_CHUNKS:
        params = {
            "season":         2026,
            "seasonType":     "postseason",
            "tournament":     "NCAA",
            "status":         "final",
            "startDateRange": start,
            "endDateRange":   end,
        }
        try:
            resp = requests.get(BASE_URL, headers=HEADERS, params=params, timeout=30)
            resp.raise_for_status()
            games = resp.json()
            for g in games:
                gid = g.get("id")
                if gid not in seen:
                    seen.add(gid)
                    all_games.append(g)
        except Exception as e:
            print(f"Error fetching games: {e}")

    return all_games

def get_round(game_notes):
    """Extract round name from gameNotes string."""
    if not game_notes:
        return "Unknown"
    notes = game_notes.lower()
    if "first four" in notes:
        return "First Four"
    if "first round" in notes:
        return "Round of 64"
    if "second round" in notes:
        return "Round of 32"
    if "sweet sixteen" in notes or "sweet 16" in notes:
        return "Sweet 16"
    if "elite eight" in notes or "elite 8" in notes:
        return "Elite 8"
    if "final four" in notes:
        return "Final Four"
    if "championship" in notes or "national championship" in notes:
        return "Championship"
    return "Unknown"

ROUND_ORDER = ["First Four", "Round of 64", "Round of 32", "Sweet 16", "Elite 8", "Final Four", "Championship", "Unknown"]

def build_grid(games):
    # Overall grid
    grid = defaultdict(lambda: defaultdict(int))
    # Per-round grids
    round_grids = defaultdict(lambda: defaultdict(lambda: defaultdict(int)))
    total = 0
    game_log = []

    for g in games:
        try:
            hp = int(g.get("homePoints") or 0)
            ap = int(g.get("awayPoints") or 0)
        except (ValueError, TypeError):
            continue
        if hp == 0 and ap == 0:
            continue
        if hp == ap:
            continue

        winner_pts = max(hp, ap)
        loser_pts  = min(hp, ap)
        wd = winner_pts % 10
        ld = loser_pts  % 10
        round_name = get_round(g.get("gameNotes", ""))

        grid[wd][ld] += 1
        round_grids[round_name][wd][ld] += 1
        total += 1

        winner_team = g.get("homeTeam") if hp > ap else g.get("awayTeam")
        loser_team  = g.get("awayTeam") if hp > ap else g.get("homeTeam")

        game_log.append({
            "date":        g.get("startDate", "")[:10],
            "round":       round_name,
            "winner":      winner_team,
            "winnerScore": winner_pts,
            "loser":       loser_team,
            "loserScore":  loser_pts,
            "square":      f"{wd}/{ld}",
        })

    # Convert to plain dicts for JSON
    def grid_to_dict(g):
        out = {}
        for w in range(10):
            out[str(w)] = {str(l): g[w][l] for l in range(10)}
        return out

    rounds_out = {}
    for round_name in ROUND_ORDER:
        if round_name in round_grids:
            rounds_out[round_name] = grid_to_dict(round_grids[round_name])

    return grid_to_dict(grid), total, game_log, rounds_out

def main():
    print("Fetching tournament games...")
    games = fetch_tournament_games()
    print(f"  {len(games)} games fetched")

    grid, total, game_log, rounds = build_grid(games)

    output = {
        "updated":    datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "season":     2026,
        "totalGames": total,
        "grid":       grid,
        "rounds":     rounds,
        "recentGames": game_log[::-1],  # all games, newest first
    }

    out_path = os.path.join(os.path.dirname(__file__), "..", "squares.json")
    with open(out_path, "w") as f:
        json.dump(output, f, indent=2)

    print(f"  Written squares.json ({total} games)")
    print(f"  Updated: {output['updated']}")

if __name__ == "__main__":
    main()
