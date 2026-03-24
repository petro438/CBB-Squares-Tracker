#!/usr/bin/env python3
"""
Fetches 2026 NCAA Tournament games from collegebasketballdata.com
and writes squares.json with winner/loser last-digit counts,
both for final scores and halftime scores.
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
                if g.get("tournament") == "NCAA" and gid not in seen:
                    seen.add(gid)
                    all_games.append(g)
        except Exception as e:
            print(f"Error fetching games: {e}")
    return all_games

def get_round(game_notes):
    if not game_notes:
        return "Unknown"
    parts = game_notes.strip().split(" - ")
    suffix = parts[-1].lower().strip() if parts else ""
    if "first four" in suffix:
        return "First Four"
    if "1st round" in suffix or "first round" in suffix:
        return "Round of 64"
    if "2nd round" in suffix or "second round" in suffix:
        return "Round of 32"
    if "sweet sixteen" in suffix or "sweet 16" in suffix:
        return "Sweet 16"
    if "elite eight" in suffix or "elite 8" in suffix:
        return "Elite 8"
    if "final four" in suffix:
        return "Final Four"
    if "national championship" in suffix or suffix == "championship":
        return "Championship"
    return "Unknown"

ROUND_ORDER = ["First Four", "Round of 64", "Round of 32", "Sweet 16", "Elite 8", "Final Four", "Championship", "Unknown"]

def parse_halftime(period_val):
    """Handles both list [49, 37] and string '49,37' formats"""
    if not period_val:
        return None
    try:
        if isinstance(period_val, list):
            return int(period_val[0])
        return int(str(period_val).split(",")[0].strip())
    except (ValueError, IndexError):
        return None

def grid_to_dict(g):
    out = {}
    for w in range(10):
        out[str(w)] = {str(l): g[w][l] for l in range(10)}
    return out

def build_grids(games):
    # Final score structures
    grid        = defaultdict(lambda: defaultdict(int))
    round_grids = defaultdict(lambda: defaultdict(lambda: defaultdict(int)))

    # Halftime score structures
    ht_grid        = defaultdict(lambda: defaultdict(int))
    ht_round_grids = defaultdict(lambda: defaultdict(lambda: defaultdict(int)))

    total    = 0
    ht_total = 0
    game_log    = []
    ht_game_log = []

    for g in games:
        try:
            hp = int(g.get("homePoints") or 0)
            ap = int(g.get("awayPoints") or 0)
        except (ValueError, TypeError):
            continue
        if hp == 0 and ap == 0 or hp == ap:
            continue

        round_name  = get_round(g.get("gameNotes", ""))
        winner_team = g.get("homeTeam") if hp > ap else g.get("awayTeam")
        loser_team  = g.get("awayTeam") if hp > ap else g.get("homeTeam")
        date_str    = g.get("startDate", "")[:10]

        # ── Final score grid ──
        wd = max(hp, ap) % 10
        ld = min(hp, ap) % 10
        grid[wd][ld] += 1
        round_grids[round_name][wd][ld] += 1
        total += 1
        game_log.append({
            "date":        date_str,
            "round":       round_name,
            "winner":      winner_team,
            "winnerScore": max(hp, ap),
            "loser":       loser_team,
            "loserScore":  min(hp, ap),
            "square":      f"{wd}/{ld}",
        })

        # ── Halftime grid ──
        home_ht = parse_halftime(g.get("homePeriodPoints") or g.get("HomePeriodPoints"))
        away_ht = parse_halftime(g.get("awayPeriodPoints") or g.get("AwayPeriodPoints"))
        if home_ht is not None and away_ht is not None and home_ht != away_ht:
            ht_winner = max(home_ht, away_ht)
            ht_loser  = min(home_ht, away_ht)
            ht_winner_team = g.get("homeTeam") if home_ht > away_ht else g.get("awayTeam")
            ht_loser_team  = g.get("awayTeam") if home_ht > away_ht else g.get("homeTeam")
            hwd = ht_winner % 10
            hld = ht_loser  % 10
            ht_grid[hwd][hld] += 1
            ht_round_grids[round_name][hwd][hld] += 1
            ht_total += 1
            ht_game_log.append({
                "date":        date_str,
                "round":       round_name,
                "winner":      ht_winner_team,
                "winnerScore": ht_winner,
                "loser":       ht_loser_team,
                "loserScore":  ht_loser,
                "square":      f"{hwd}/{hld}",
            })

    # Build round dicts
    rounds_out = {}
    ht_rounds_out = {}
    for rn in ROUND_ORDER:
        if rn in round_grids:
            rounds_out[rn] = grid_to_dict(round_grids[rn])
        if rn in ht_round_grids:
            ht_rounds_out[rn] = grid_to_dict(ht_round_grids[rn])

    return (
        grid_to_dict(grid), total, game_log, rounds_out,
        grid_to_dict(ht_grid), ht_total, ht_game_log, ht_rounds_out
    )

def main():
    print("Fetching tournament games...")
    games = fetch_tournament_games()
    print(f"  {len(games)} games fetched")

    grid, total, game_log, rounds, ht_grid, ht_total, ht_game_log, ht_rounds = build_grids(games)

    output = {
        "updated":      datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "season":       2026,
        "totalGames":   total,
        "grid":         grid,
        "rounds":       rounds,
        "recentGames":  game_log[::-1],
        "halftime": {
            "totalGames":  ht_total,
            "grid":        ht_grid,
            "rounds":      ht_rounds,
            "recentGames": ht_game_log[::-1],
        }
    }

    out_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "squares.json")
    with open(out_path, "w") as f:
        json.dump(output, f, indent=2)

    print(f"  Written squares.json ({total} final, {ht_total} halftime)")
    print(f"  Updated: {output['updated']}")

if __name__ == "__main__":
    main()
