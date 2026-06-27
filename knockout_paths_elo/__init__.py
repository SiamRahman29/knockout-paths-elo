"""Knockout paths ELO analysis package."""

from knockout_paths_elo.elo_scraper import scrape_world_cup_teams
from knockout_paths_elo.fifa_scraper import scrape_world_cup_fifa_rankings

__all__ = ["scrape_world_cup_teams", "scrape_world_cup_fifa_rankings"]
