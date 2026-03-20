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
                # Filter to NCAA tournament only client-side
                if g.get("tournament") == "NCAA" and gid not in seen:
                    seen.add(gid)
                    all_games.append(g)
        except Exception as e:
            print(f"Error fetching games: {e}")

    return all_games

def build_grid(games):
    grid = defaultdict(lambda: defaultdict(int))
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

        grid[wd][ld] += 1
        total += 1

        winner_team = g.get("homeTeam") if hp > ap else g.get("awayTeam")
        loser_team  = g.get("awayTeam") if hp > ap else g.get("homeTeam")

        game_log.append({
            "date":        g.get("startDate", "")[:10],
            "winner":      winner_team,
            "winnerScore": winner_pts,
            "loser":       loser_team,
            "loserScore":  loser_pts,
            "square":      f"{wd}/{ld}",
        })

    # Convert to plain dict for JSON
    grid_out = {}
    for w in range(10):
        grid_out[str(w)] = {}
        for l in range(10):
            grid_out[str(w)][str(l)] = grid[w][l]

    return grid_out, total, game_log

def main():
    print("Fetching tournament games...")
    games = fetch_tournament_games()
    print(f"  {len(games)} games fetched")

    grid, total, game_log = build_grid(games)

    output = {
        "updated":   datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "season":    2026,
        "totalGames": total,
        "grid":      grid,
        "recentGames": game_log[-10:][::-1],  # last 10, newest first
    }

    out_path = os.path.join(os.path.dirname(__file__), "..", "squares.json")
    with open(out_path, "w") as f:
        json.dump(output, f, indent=2)

    print(f"  Written squares.json ({total} games)")
    print(f"  Updated: {output['updated']}")

if __name__ == "__main__":
    main()