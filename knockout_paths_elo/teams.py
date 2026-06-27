"""Shared helpers for parsing team_list.txt and resolving team names."""

from __future__ import annotations

import re
import unicodedata
from pathlib import Path


def normalize_name(name: str) -> str:
    text = unicodedata.normalize("NFKD", name)
    text = text.encode("ascii", "ignore").decode("ascii")
    return re.sub(r"\s+", " ", text.lower()).strip()


def load_team_list(path: str | Path) -> list[tuple[str, str]]:
    """Parse data/team_list.txt into (group, team_name) pairs."""
    teams: list[tuple[str, str]] = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or "|" not in line:
            continue
        group_part, team_part = line.split("|", 1)
        group = group_part.strip()
        for name in re.split(r"\s{2,}", team_part.strip()):
            name = name.strip()
            if name:
                teams.append((group, name))
    return teams


def lookup_name(name: str, aliases: dict[str, str]) -> str:
    return aliases.get(name, name)
