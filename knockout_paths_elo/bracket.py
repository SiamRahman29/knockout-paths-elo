"""Build the World Cup knockout bracket as a binary tree and analyse it.

The Round of 32 is modelled as a perfect binary tree: 32 leaves (the teams)
and 31 internal nodes (the matches). From this tree we derive two things off
the Elo ratings in ``data/elo_ratings.csv``:

* **Most probable winner** - the champion probability for every team, computed
  by propagating each subtree's "who emerges from here" distribution up to the
  root (a standard bracket dynamic program).
* **Most difficult path** - each team's strength of schedule, i.e. the expected
  Elo of the opponents it would have to beat on its road to the title, weighted
  by how likely each potential opponent is to actually be there.

Run as a script for a full report::

    python -m knockout_paths_elo.bracket
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

# A probability model: P(team A beats team B) given their two ratings.
ProbFn = Callable[[float, float], float]

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
ELO_CSV = DATA_DIR / "elo_ratings.csv"

ROUND_NAMES = {32: "R32", 16: "R16", 8: "QF", 4: "SF", 2: "Final"}


# --------------------------------------------------------------------------- #
# Tree
# --------------------------------------------------------------------------- #
@dataclass
class BracketNode:
    """A node in the knockout binary tree.

    A leaf holds a single ``team``. An internal node is a match between the
    winners emerging from its ``left`` and ``right`` subtrees; ``size`` is the
    number of leaves below it (32 at the root, 1 at a leaf).
    """

    team: str | None = None
    left: "BracketNode | None" = None
    right: "BracketNode | None" = None

    @property
    def is_leaf(self) -> bool:
        return self.left is None and self.right is None

    @property
    def size(self) -> int:
        if self.is_leaf:
            return 1
        return self.left.size + self.right.size

    @property
    def round_name(self) -> str:
        return ROUND_NAMES.get(self.size, f"{self.size}-team")

    def leaves(self) -> list["BracketNode"]:
        if self.is_leaf:
            return [self]
        return self.left.leaves() + self.right.leaves()


def build_bracket(teams: list[str]) -> BracketNode:
    """Build a perfect binary tree whose leaves are ``teams`` (in bracket order).

    The list length must be a power of two (32 for a World Cup R32). Adjacent
    pairs meet in the first round, so the caller controls the matchups via the
    ordering of ``teams``.
    """
    n = len(teams)
    if n == 0 or (n & (n - 1)) != 0:
        raise ValueError(f"expected a power-of-two number of teams, got {n}")

    nodes = [BracketNode(team=t) for t in teams]
    while len(nodes) > 1:
        nodes = [
            BracketNode(left=nodes[i], right=nodes[i + 1])
            for i in range(0, len(nodes), 2)
        ]
    return nodes[0]


# --------------------------------------------------------------------------- #
# Official FIFA World Cup 2026 Round of 32
# --------------------------------------------------------------------------- #
# The bottommost layer of the bracket: the 16 first-round matchups, in official
# bracket order so that adjacent pairs feed the same Round-of-16 match, those
# feed the same quarter-final, and so on up to the final. This is all we hard
# code -- who advances at every layer above is decided by Elo. Match numbers
# (M73-M88) are noted for traceability; team names match the "team" column of
# data/elo_ratings.csv.
R32_MATCHUPS: list[tuple[str, str]] = [
    ("Germany", "Paraguay"),            # M74  ┐ R16 M89 ┐ QF M97  ┐ SF M101 ┐
    ("France", "Sweden"),               # M77  ┘         │         │         │
    ("South Africa", "Canada"),         # M73  ┐ R16 M90 ┘         │         │
    ("Netherlands", "Morocco"),         # M75  ┘                   │         │
    ("Portugal", "Croatia"),            # M83  ┐ R16 M93 ┐ QF M98  ┘         │
    ("Spain", "Austria"),               # M84  ┘         │                   │
    ("USA", "Bosnia & Herzegovina"),    # M81  ┐ R16 M94 ┘                   │
    ("Belgium", "Senegal"),             # M82  ┘                          Final
    ("Brazil", "Japan"),                # M76  ┐ R16 M91 ┐ QF M99  ┐ SF M102 │
    ("Ivory Coast", "Norway"),          # M78  ┘         │         │         │
    ("Mexico", "Ecuador"),              # M79  ┐ R16 M92 ┘         │         │
    ("England", "DR Congo"),            # M80  ┘                   │         │
    ("Argentina", "Cape Verde"),        # M86  ┐ R16 M95 ┐ QF M100 ┘         │
    ("Australia", "Egypt"),             # M88  ┘         │                   │
    ("Switzerland", "Algeria"),         # M85  ┐ R16 M96 ┘                   ┘
    ("Colombia", "Ghana"),              # M87  ┘
]


def build_official_bracket() -> BracketNode:
    """Build the official FIFA World Cup 2026 knockout tree (R32 -> Final)."""
    leaves = [team for match in R32_MATCHUPS for team in match]
    return build_bracket(leaves)


# --------------------------------------------------------------------------- #
# Elo helpers
# --------------------------------------------------------------------------- #
def load_ratings(path: str | Path = ELO_CSV) -> pd.DataFrame:
    """Load the Elo table; columns we rely on: group, team, rating."""
    return pd.read_csv(path)


def win_probability(elo_a: float, elo_b: float) -> float:
    """Elo expected score: P(team A beats team B), draws split evenly.

    Uses the classic /400 scale. FIFA's own ranking formula instead divides by
    600; pass :func:`fifa_win_probability` (or any :data:`ProbFn`) to the
    analysis functions to use that model with FIFA points.
    """
    return 1.0 / (1.0 + 10.0 ** (-(elo_a - elo_b) / 400.0))


def fifa_win_probability(points_a: float, points_b: float) -> float:
    """FIFA ranking expected result: P(A beats B) on the /600 points scale."""
    return 1.0 / (1.0 + 10.0 ** (-(points_a - points_b) / 600.0))


# --------------------------------------------------------------------------- #
# Analysis
# --------------------------------------------------------------------------- #
def advancement_distribution(
    node: BracketNode, ratings: dict[str, float], prob: ProbFn = win_probability
) -> dict[str, float]:
    """Probability that each team emerges as the winner of ``node``'s subtree."""
    if node.is_leaf:
        return {node.team: 1.0}

    left = advancement_distribution(node.left, ratings, prob)
    right = advancement_distribution(node.right, ratings, prob)

    dist: dict[str, float] = {}
    for a, pa in left.items():
        for b, pb in right.items():
            p_meet = pa * pb
            p_a_wins = prob(ratings[a], ratings[b])
            dist[a] = dist.get(a, 0.0) + p_meet * p_a_wins
            dist[b] = dist.get(b, 0.0) + p_meet * (1.0 - p_a_wins)
    return dist


def champion_probabilities(
    root: BracketNode, ratings: dict[str, float], prob: ProbFn = win_probability
) -> dict[str, float]:
    """Title probability for every team (the root's advancement distribution)."""
    return advancement_distribution(root, ratings, prob)


@dataclass
class PathStep:
    round_name: str
    exp_opponent_rating: float
    exp_win_prob: float


@dataclass
class PathDifficulty:
    team: str
    steps: list[PathStep] = field(default_factory=list)

    @property
    def strength_of_schedule(self) -> float:
        """Sum of expected opponent rating across all rounds (higher = harder)."""
        return sum(s.exp_opponent_rating for s in self.steps)

    @property
    def run_the_table_prob(self) -> float:
        """P(team wins every match on this path) = product of round win probs."""
        p = 1.0
        for s in self.steps:
            p *= s.exp_win_prob
        return p


def path_difficulty(
    root: BracketNode,
    team: str,
    ratings: dict[str, float],
    prob: ProbFn = win_probability,
) -> PathDifficulty:
    """Expected opponent quality round-by-round on ``team``'s road to the title.

    For each match on the path, the opponent is the winner of the sibling
    subtree, so the expected opponent rating and win probability are weighted by
    each rival's chance of actually being there. ``prob`` selects the model
    (Elo by default; pass :func:`fifa_win_probability` for FIFA points).
    """
    # Locate the path of nodes from the team's leaf up to the root.
    path: list[BracketNode] = []

    def find(node: BracketNode) -> bool:
        path.append(node)
        if node.is_leaf:
            if node.team == team:
                return True
        else:
            if find(node.left) or find(node.right):
                return True
        path.pop()
        return False

    if not find(root):
        raise KeyError(f"team {team!r} is not in the bracket")

    result = PathDifficulty(team=team)
    for parent, child in zip(path, path[1:]):
        sibling = parent.right if parent.left is child else parent.left
        opp_dist = advancement_distribution(sibling, ratings, prob)
        exp_rating = sum(opp_dist[o] * ratings[o] for o in opp_dist)
        exp_win = sum(
            opp_dist[o] * prob(ratings[team], ratings[o]) for o in opp_dist
        )
        result.steps.append(PathStep(parent.round_name, exp_rating, exp_win))

    result.steps.reverse()  # report R32 -> Final
    return result


# --------------------------------------------------------------------------- #
# Report
# --------------------------------------------------------------------------- #
def _report() -> None:
    ratings_df = load_ratings()
    rating_of = dict(zip(ratings_df["team"], ratings_df["rating"]))

    root = build_official_bracket()
    qualifiers = [leaf.team for leaf in root.leaves()]

    print(
        f"Official 2026 knockout tree: {root.size} leaves, round = {root.round_name}\n"
    )

    champs = champion_probabilities(root, rating_of)
    print("Most probable winner (top 10):")
    for i, (team, p) in enumerate(
        sorted(champs.items(), key=lambda x: x[1], reverse=True)[:10], 1
    ):
        print(f"  {i:2}. {team:<22} {p:6.1%}   (Elo {rating_of[team]:.0f})")

    paths = [path_difficulty(root, t, rating_of) for t in qualifiers]
    paths.sort(key=lambda p: p.strength_of_schedule, reverse=True)
    print("\nMost difficult path (by expected opponent Elo, top 10):")
    for i, pd_ in enumerate(paths[:10], 1):
        print(
            f"  {i:2}. {pd_.team:<22} SoS {pd_.strength_of_schedule:.0f}"
            f"   run-the-table {pd_.run_the_table_prob:.2%}"
        )

    hardest = paths[0]
    print(f"\nRound-by-round road for {hardest.team} (hardest path):")
    for step in hardest.steps:
        print(
            f"  {step.round_name:<6} exp opp Elo {step.exp_opponent_rating:7.0f}"
            f"   win prob {step.exp_win_prob:5.1%}"
        )


if __name__ == "__main__":
    _report()
