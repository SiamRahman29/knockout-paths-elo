#!/usr/bin/env python3
"""Scrape FIFA men's world rankings for FIFA World Cup 2026 teams."""

from pathlib import Path

from knockout_paths_elo.fifa_scraper import scrape_world_cup_fifa_rankings


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    team_list = root / "data" / "team_list.txt"
    output_dir = root / "data"

    df = scrape_world_cup_fifa_rankings(
        team_list_path=team_list,
        output_dir=output_dir,
    )

    print(f"Scraped FIFA rankings for {len(df)} teams -> {output_dir / 'fifa_rankings.csv'}")
    if not df.empty:
        print(f"Last official update: {df['ranking_date'].iloc[0]}")
    print()
    print(
        df[["group", "team", "rank", "rank_movement", "decimal_total_points", "points_change", "confederation"]]
        .to_string(index=False)
    )


if __name__ == "__main__":
    main()
