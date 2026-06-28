# knockout-paths-elo

Which team has the **hardest road to winning the 2026 FIFA World Cup**?

Not "who's the best team" — but "who got the unluckiest bracket." A great team
with an easy path has it simpler than a good team that has to beat three giants
in a row. This repo measures that.

## The idea (ELI5)

The 32-team knockout bracket is just a tournament tree: win your match, move up,
keep winning until you lift the trophy. We:

1. Take the **real, official 2026 knockout matchups** (hard-coded) and build them
   into a binary tree.
2. Rate every team using two independent rating systems.
3. For each team, walk its path to the final. At every round we don't know the
   exact opponent yet, so we compute the **expected opponent** — weighted by how
   likely each possible rival is to actually be there.
4. Add it up into a "strength of schedule" number. Higher = harder road.

We also fall out a bonus: each team's chance of **winning the whole thing**
(propagating win probabilities up the tree).

## What we tried

- **Two rating systems, side by side** so results don't depend on one source:
  - **Elo** (eloratings.net) — win probability on the classic `/400` scale.
  - **FIFA ranking points** — win probability on FIFA's `/600` scale.
- **Three difficulty angles:** average opponent Elo, average opponent FIFA
  points, and average opponent FIFA rank-number.
- **Scrapers** to pull fresh Elo ratings and FIFA rankings for all 48 World Cup
  teams (`scripts/`, output in `data/`).
- Modeled the bracket as a **binary tree** with a clean dynamic program for both
  "who advances" and "expected opponent each round" (`knockout_paths_elo/bracket.py`).

## Layout

```
knockout_paths_elo/   # the package
  bracket.py          # tree + path-difficulty + champion-probability math
  elo_scraper.py      # eloratings.net scraper
  fifa_scraper.py     # FIFA rankings scraper
  teams.py            # team-name parsing/normalization helpers
scripts/              # run the scrapers
data/                 # scraped CSVs + team/group lists
notebooks/
  hardest_routes.ipynb  # the analysis & charts
```

## Run it

```bash
pip install -e .

# Quick text report (top winners + hardest paths):
python -m knockout_paths_elo.bracket

# Refresh the data:
python scripts/scrape_elo_ratings.py
python scripts/scrape_fifa_rankings.py

# Full analysis with charts:
jupyter notebook notebooks/hardest_routes.ipynb
```

## Data sources

- Elo: <https://www.eloratings.net>
- FIFA rankings: <https://inside.fifa.com/fifa-world-ranking/men>
- Bracket: [2026 FIFA World Cup knockout stage](https://en.wikipedia.org/wiki/2026_FIFA_World_Cup_knockout_stage)
