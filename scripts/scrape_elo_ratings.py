#!/usr/bin/env python3
"""Scrape eloratings.net data for FIFA World Cup 2026 teams."""

from pathlib import Path

from knockout_paths_elo.elo_scraper import scrape_world_cup_teams


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    team_list = root / "data" / "team_list.txt"
    output_dir = root / "data"

    ratings_df, matches_df = scrape_world_cup_teams(
        team_list_path=team_list,
        output_dir=output_dir,
        include_matches=True,
    )

    print(f"Scraped ratings for {len(ratings_df)} teams -> {output_dir / 'elo_ratings.csv'}")
    if matches_df is not None:
        print(f"Scraped {len(matches_df)} match rows -> {output_dir / 'elo_match_history.csv'}")
    print()
    print(ratings_df[["group", "team", "global_rank", "rating", "matches_total", "wins", "losses", "draws"]].to_string(index=False))


if __name__ == "__main__":
    main()
