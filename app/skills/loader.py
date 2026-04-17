from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from loguru import logger

_SKILLS_DIR = Path(__file__).parent


class SkillsLoader:
    """
    Loads Markdown skill files from the skills directory and caches them.

    Skills are plain Markdown files that define prompt policies,
    routing rules, diagnostic heuristics, and answer style guidelines.
    Agents receive relevant skill text as system prompt additions.
    """

    def __init__(self, skills_dir: Path = _SKILLS_DIR) -> None:
        self._dir = skills_dir
        self._cache: dict[str, str] = {}
        self._load_all()

    def _load_all(self) -> None:
        for md_file in self._dir.glob("*.md"):
            skill_name = md_file.stem
            try:
                self._cache[skill_name] = md_file.read_text(encoding="utf-8")
                logger.debug(f"Loaded skill: {skill_name}")
            except Exception as exc:
                logger.warning(f"Could not load skill '{skill_name}': {exc}")

    def get(self, skill_name: str, default: str = "") -> str:
        """Return skill content by file stem (without .md extension)."""
        return self._cache.get(skill_name, default)

    def all_names(self) -> list[str]:
        return list(self._cache.keys())

    def reload(self) -> None:
        """Re-read all skill files from disk (useful during development)."""
        self._cache.clear()
        self._load_all()


@lru_cache(maxsize=1)
def get_skills_loader() -> SkillsLoader:
    return SkillsLoader()
