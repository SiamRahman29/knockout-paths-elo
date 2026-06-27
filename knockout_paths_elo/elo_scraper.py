"""Scrape team ratings and match history from eloratings.net."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path

import pandas as pd
import requests

BASE_URL = "https://eloratings.net"

RATING_COLUMNS = [
    "local_rank",
    "global_rank",
    "team_code",
    "rating",
    "rank_highest",
    "rating_highest",
    "rank_average",
    "rating_average",
    "rank_lowest",
    "rating_lowest",
    "rank_change_3m",
    "rating_change_3m",
    "rank_change_6m",
    "rating_change_6m",
    "rank_change_1y",
    "rating_change_1y",
    "rank_change_2y",
    "rating_change_2y",
    "rank_change_5y",
    "rating_change_5y",
    "rank_change_10y",
    "rating_change_10y",
    "matches_total",
    "matches_home",
    "matches_away",
    "matches_neutral",
    "wins",
    "losses",
    "draws",
    "goals_for",
    "goals_against",
    "rank_change_ytd",
    "rating_change_ytd",
]

MATCH_COLUMNS = [
    "year",
    "month",
    "day",
    "home_code",
    "away_code",
    "home_score",
    "away_score",
    "tournament_code",
    "venue_code",
    "rating_change",
    "home_rating",
    "away_rating",
    "home_rating_change",
    "away_rating_change",
    "home_rank",
    "away_rank",
]

from knockout_paths_elo.teams import load_team_list, lookup_name

# Names in team_list.txt that differ from eloratings.net canonical labels.
ELO_TEAM_ALIASES: dict[str, str] = {
    "USA": "United States",
    "Czech Republic": "Czechia",
    "Bosnia & Herzegovina": "Bosnia and Herzegovina",
}


@dataclass(frozen=True)
class TeamInfo:
    list_name: str
    code: str
    canonical_name: str
    page: str
    group: str


def page_name(text: str) -> str:
    """Mirror eloratings.net pageName() for team page URLs."""
    if not text:
        return ""
    text = text.replace(" ", "_")
    text = unicodedata.normalize("NFKD", text)
    text = text.encode("ascii", "ignore").decode("ascii")
    replacements = [
        (r"[àáâãäå]", "a"),
        (r"ç", "c"),
        (r"[èéêë]", "e"),
        (r"[ìíîï]", "i"),
        (r"[òóôõö]", "o"),
        (r"[ùúûü]", "u"),
        (r"ñ", "n"),
    ]
    for pattern, replacement in replacements:
        text = re.sub(pattern, replacement, text)
    return text


def _fetch_text(path: str, session: requests.Session) -> str:
    response = session.get(f"{BASE_URL}/{path}", timeout=30)
    response.raise_for_status()
    response.encoding = "utf-8"
    return response.text

def load_dictionaries(session: requests.Session) -> tuple[dict[str, str], dict[str, list[str]], dict[str, list[str]]]:
    """Load successor map, team names, and tournament names."""
    successor: dict[str, str] = {}
    for line in _fetch_text("teams.tsv", session).splitlines():
        if not line.strip():
            continue
        old, new = line.split("\t", 1)
        successor[old] = new

    team_dictionary: dict[str, list[str]] = {}
    for line in _fetch_text("en.teams.tsv", session).splitlines():
        if not line.strip():
            continue
        parts = line.split("\t")
        code = parts[0]
        if code.endswith("_loc"):
            continue
        team_dictionary[code] = parts[1:]

    tournament_dictionary: dict[str, list[str]] = {}
    for line in _fetch_text("en.tournaments.tsv", session).splitlines():
        if not line.strip():
            continue
        parts = line.split("\t")
        tournament_dictionary[parts[0]] = parts[1:]

    return successor, team_dictionary, tournament_dictionary


def resolve_team_code(name: str, team_dictionary: dict[str, list[str]]) -> str | None:
    """Map a team_list.txt name to an eloratings.net team code."""
    lookup = lookup_name(name, ELO_TEAM_ALIASES).lower()
    for code, names in team_dictionary.items():
        for variant in names:
            if variant.lower() == lookup:
                return code
    for code, names in team_dictionary.items():
        for variant in names:
            v = variant.lower()
            if lookup in v or v in lookup:
                return code
    return None


def resolve_teams(
    team_list_path: str | Path,
    session: requests.Session | None = None,
) -> list[TeamInfo]:
    session = session or requests.Session()
    _, team_dictionary, _ = load_dictionaries(session)
    resolved: list[TeamInfo] = []
    for group, name in load_team_list(team_list_path):
        code = resolve_team_code(name, team_dictionary)
        if code is None:
            raise ValueError(f"Could not resolve eloratings.net code for team: {name!r}")
        canonical = team_dictionary[code][0]
        resolved.append(
            TeamInfo(
                list_name=name,
                code=code,
                canonical_name=canonical,
                page=page_name(canonical),
                group=group,
            )
        )
    return resolved


def _parse_change(value: str) -> int | None:
    value = value.strip()
    if not value or value in {"−", "–", "-"}:
        return None
    value = value.replace("−", "-").replace("–", "-")
    if value.startswith("+"):
        return int(value[1:])
    return int(value)


def parse_ratings_tsv(text: str) -> dict[str, dict[str, object]]:
    """Parse World.tsv (or similar) into a dict keyed by team code."""
    rows: dict[str, dict[str, object]] = {}
    for line in text.splitlines():
        if not line.strip():
            continue
        fields = line.split("\t")
        if len(fields) < len(RATING_COLUMNS) - 2:
            continue
        padded = fields + [None] * max(0, len(RATING_COLUMNS) - len(fields))
        row = dict(zip(RATING_COLUMNS, padded[: len(RATING_COLUMNS)]))
        code = row["team_code"]
        for key in (
            "local_rank",
            "global_rank",
            "rating",
            "rank_highest",
            "rating_highest",
            "rank_average",
            "rating_average",
            "rank_lowest",
            "rating_lowest",
            "matches_total",
            "matches_home",
            "matches_away",
            "matches_neutral",
            "wins",
            "losses",
            "draws",
            "goals_for",
            "goals_against",
        ):
            row[key] = int(row[key])
        for key in (
            "rank_change_3m",
            "rating_change_3m",
            "rank_change_6m",
            "rating_change_6m",
            "rank_change_1y",
            "rating_change_1y",
            "rank_change_2y",
            "rating_change_2y",
            "rank_change_5y",
            "rating_change_5y",
            "rank_change_10y",
            "rating_change_10y",
            "rank_change_ytd",
            "rating_change_ytd",
        ):
            if row.get(key) is not None:
                row[key] = _parse_change(str(row[key]))
        rows[str(code)] = row
    return rows


def parse_match_tsv(text: str) -> list[dict[str, object]]:
    """Parse a team page TSV into match records."""
    matches: list[dict[str, object]] = []
    for line in text.splitlines():
        if not line.strip():
            continue
        fields = line.split("\t")
        if len(fields) < 16:
            continue
        row = dict(zip(MATCH_COLUMNS, fields[: len(MATCH_COLUMNS)]))
        for key in ("year", "month", "day", "home_score", "away_score"):
            row[key] = int(row[key])
        for key in (
            "rating_change",
            "home_rating",
            "away_rating",
            "home_rating_change",
            "away_rating_change",
            "home_rank",
            "away_rank",
        ):
            row[key] = _parse_change(str(row[key]))
        matches.append(row)
    return matches


def code_to_name(
    code: str,
    team_dictionary: dict[str, list[str]],
    successor: dict[str, str],
) -> str:
    code = successor.get(code, code)
    return team_dictionary.get(code, [code])[0]


def scrape_world_cup_teams(
    team_list_path: str | Path = "data/team_list.txt",
    output_dir: str | Path = "data",
    include_matches: bool = True,
    session: requests.Session | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame | None]:
    """
    Scrape eloratings.net for all teams in team_list.txt.

    Returns (ratings_df, matches_df). Writes CSV files to output_dir when provided.
    """
    session = session or requests.Session()
    output_dir = Path(output_dir)
    teams = resolve_teams(team_list_path, session)
    successor, team_dictionary, tournament_dictionary = load_dictionaries(session)

    world_text = _fetch_text("World.tsv", session)
    ratings_by_code = parse_ratings_tsv(world_text)

    ratings_rows: list[dict[str, object]] = []
    match_rows: list[dict[str, object]] = []

    for team in teams:
        rating = ratings_by_code.get(team.code)
        if rating is None:
            raise ValueError(f"No World.tsv rating row found for {team.list_name} ({team.code})")

        ratings_rows.append(
            {
                "group": team.group,
                "team": team.list_name,
                "canonical_name": team.canonical_name,
                "team_code": team.code,
                **{k: v for k, v in rating.items() if k != "team_code"},
            }
        )

        if not include_matches:
            continue

        match_text = _fetch_text(f"{team.page}.tsv", session)
        for match in parse_match_tsv(match_text):
            tournament_code = str(match["tournament_code"])
            match_rows.append(
                {
                    "team": team.list_name,
                    "team_code": team.code,
                    "year": match["year"],
                    "month": match["month"],
                    "day": match["day"],
                    "home_team": code_to_name(str(match["home_code"]), team_dictionary, successor),
                    "away_team": code_to_name(str(match["away_code"]), team_dictionary, successor),
                    "home_score": match["home_score"],
                    "away_score": match["away_score"],
                    "tournament": tournament_dictionary.get(tournament_code, [tournament_code])[0],
                    "tournament_code": tournament_code,
                    "venue": code_to_name(str(match["venue_code"]), team_dictionary, successor)
                    if match["venue_code"]
                    else None,
                    "home_rating": match["home_rating"],
                    "away_rating": match["away_rating"],
                    "home_rating_change": match["home_rating_change"],
                    "away_rating_change": match["away_rating_change"],
                    "home_rank": match["home_rank"],
                    "away_rank": match["away_rank"],
                }
            )

    ratings_df = pd.DataFrame(ratings_rows).sort_values(["group", "team"]).reset_index(drop=True)
    matches_df = pd.DataFrame(match_rows) if include_matches else None

    output_dir.mkdir(parents=True, exist_ok=True)
    ratings_path = output_dir / "elo_ratings.csv"
    ratings_df.to_csv(ratings_path, index=False)

    if matches_df is not None:
        matches_path = output_dir / "elo_match_history.csv"
        matches_df.to_csv(matches_path, index=False)

    return ratings_df, matches_df
