from __future__ import annotations

from typing import Any

from app.skills.loader import SkillLoader


class SkillRegistry(SkillLoader):
    """Compatibility wrapper around the Cursor-style skill loader."""

    def retrieve_context(
        self,
        profile: dict[str, Any],
        user_message: str,
        *,
        max_snippets: int | None = None,
        skill_id: str = "converse_with_profile",
    ) -> list[dict[str, Any]]:
        return super().retrieve_context(
            skill_id,
            profile,
            user_message,
            max_snippets=max_snippets,
        )
