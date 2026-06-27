"""Scrape FIFA/Coca-Cola Men's World Ranking for World Cup teams."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import requests

from knockout_paths_elo.teams import load_team_list, lookup_name, normalize_name

BASE_URL = "https://api.fifa.com/api/v3/rankings"
MENS_GENDER = 1

FIFA_TEAM_ALIASES: dict[str, str] = {
    "USA": "USA",
    "Czech Republic": "Czechia",
    "Bosnia & Herzegovina": "Bosnia and Herzegovina",
    "South Korea": "Korea Republic",
    "Ivory Coast": "Côte d'Ivoire",
    "DR Congo": "Congo DR",
    "Cape Verde": "Cabo Verde",
    "Turkey": "Türkiye",
    "Iran": "IR Iran",
}


def _fetch_rankings(session: requests.Session, count: int = 300) -> list[dict]:
    response = session.get(
        BASE_URL,
        params={"gender": MENS_GENDER, "count": count},
        timeout=30,
        headers={"User-Agent": "Mozilla/5.0"},
    )
    response.raise_for_status()
    payload = response.json()
    return payload.get("Results", [])


def _team_name(entry: dict) -> str:
    for item in entry.get("TeamName", []):
        if item.get("Locale", "").startswith("en"):
            return item["Description"]
    return entry["TeamName"][0]["Description"]


def _build_lookup(rankings: list[dict]) -> dict[str, dict]:
    lookup: dict[str, dict] = {}
    for entry in rankings:
        name = _team_name(entry)
        lookup[normalize_name(name)] = entry
    return lookup


def resolve_fifa_entry(name: str, lookup: dict[str, dict]) -> dict | None:
    """Map a team_list.txt name to a FIFA rankings API entry."""
    candidates = [
        lookup_name(name, FIFA_TEAM_ALIASES),
        name,
    ]
    for candidate in candidates:
        entry = lookup.get(normalize_name(candidate))
        if entry is not None:
            return entry

    target = normalize_name(lookup_name(name, FIFA_TEAM_ALIASES))
    for key, entry in lookup.items():
        if target in key or key in target:
            return entry
    return None


def _parse_entry(entry: dict) -> dict[str, object]:
    points = entry.get("DecimalTotalPoints", entry.get("TotalPoints"))
    prev_points = entry.get("DecimalPrevPoints", entry.get("PrevPoints"))
    points_change = None
    if points is not None and prev_points is not None:
        points_change = round(float(points) - float(prev_points), 2)

    return {
        "fifa_name": _team_name(entry),
        "country_code": entry.get("IdCountry"),
        "confederation": entry.get("ConfederationName"),
        "rank": entry.get("Rank"),
        "previous_rank": entry.get("PrevRank"),
        "rank_movement": entry.get("RankingMovement"),
        "end_of_year_rank": entry.get("EOYRank"),
        "total_points": entry.get("TotalPoints"),
        "decimal_total_points": entry.get("DecimalTotalPoints"),
        "previous_points": entry.get("PrevPoints"),
        "decimal_previous_points": entry.get("DecimalPrevPoints"),
        "points_change": points_change,
        "end_of_year_points": entry.get("EOYPoints"),
        "decimal_end_of_year_points": entry.get("DecimalEOYPoints"),
        "matches_counted": entry.get("Matches"),
        "ranking_date": entry.get("PubDate"),
        "previous_ranking_date": entry.get("PrePubDate"),
        "end_of_year_ranking_date": entry.get("EOYPubDate"),
    }


def scrape_world_cup_fifa_rankings(
    team_list_path: str | Path = "data/team_list.txt",
    output_dir: str | Path = "data",
    session: requests.Session | None = None,
) -> pd.DataFrame:
    """
    Scrape FIFA men's world rankings for teams in team_list.txt.

    Data source: https://inside.fifa.com/fifa-world-ranking/men
    API: https://api.fifa.com/api/v3/rankings?gender=1
    """
    session = session or requests.Session()
    output_dir = Path(output_dir)
    rankings = _fetch_rankings(session)
    lookup = _build_lookup(rankings)

    rows: list[dict[str, object]] = []
    for group, name in load_team_list(team_list_path):
        entry = resolve_fifa_entry(name, lookup)
        if entry is None:
            raise ValueError(f"No FIFA ranking found for team: {name!r}")
        rows.append({"group": group, "team": name, **_parse_entry(entry)})

    df = pd.DataFrame(rows).sort_values(["group", "team"]).reset_index(drop=True)

    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "fifa_rankings.csv"
    df.to_csv(output_path, index=False)
    return df
