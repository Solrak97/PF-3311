from __future__ import annotations

from typing import Any

from app.brain.embeddings import cosine_similarity, embed_text
from app.profiles.store import ProfileStore
from app.skills.loader import SkillLoader, _sample_dicts

CONVERSATION_SKILL_ID = "converse_with_profile"


def _match_voice_exemplars(
    yaml_profile: dict[str, Any] | None,
    situation: str,
    *,
    limit: int,
) -> list[dict[str, Any]]:
    if not isinstance(yaml_profile, dict):
        return []
    exemplars = yaml_profile.get("voice_exemplars") or []
    if not isinstance(exemplars, list):
        return []
    matched: list[dict[str, Any]] = []
    fallback: list[dict[str, Any]] = []
    for item in exemplars:
        if not isinstance(item, dict):
            continue
        line = str(item.get("line", "")).strip()
        if not line:
            continue
        context = str(item.get("context", "")).strip().lower()
        entry = {
            "id": f"ex-{context or 'voice'}",
            "situation": context or "open",
            "summary": f"Voice exemplar ({context})",
            "exemplar_line": line,
            "source": "voice_exemplar",
        }
        fallback.append(entry)
        if situation and (context == situation or situation in context or context in situation):
            matched.append(entry)
    pool = matched or fallback
    return pool[:limit]


async def retrieve_examples(
    profile_store: ProfileStore,
    profile_id: str,
    *,
    user_message: str,
    situation: str = "open",
    yaml_profile: dict[str, Any] | None = None,
    skills: SkillLoader | None = None,
    max_snippets: int = 3,
    match_on: str = "category",
) -> tuple[list[dict[str, Any]], bool]:
    """Skill 4: retrieve similar moments and voice exemplars."""
    registry = skills or SkillLoader()
    skill = registry.get(CONVERSATION_SKILL_ID)
    retrieval = skill.data.get("retrieval") or {}
    limit = max_snippets or int(retrieval.get("max_snippets", 3))
    match_mode = match_on or str(retrieval.get("match_on", "category"))

    moments_index = profile_store.load_moments(profile_id)
    moments = (moments_index or {}).get("moments") or []
    candidates: list[dict[str, Any]] = []
    if isinstance(moments, list):
        for moment in moments:
            if not isinstance(moment, dict):
                continue
            if match_mode == "category" and situation and situation != "open":
                moment_situation = str(moment.get("situation", "")).lower()
                if moment_situation and moment_situation != situation and situation not in moment_situation:
                    continue
            candidates.append(moment)

    query_embedding = await embed_text(f"{situation} {user_message}")
    scored: list[tuple[float, dict[str, Any]]] = []
    if query_embedding and candidates:
        for moment in candidates:
            emb = moment.get("embedding")
            if isinstance(emb, list) and emb:
                score = cosine_similarity(query_embedding, [float(x) for x in emb])
            else:
                text = f"{moment.get('summary', '')} {moment.get('response', '')}".lower()
                score = sum(1 for word in user_message.lower().split() if len(word) > 3 and word in text)
            scored.append((score, moment))
        scored.sort(key=lambda x: x[0], reverse=True)
        retrieved = [item for score, item in scored[:limit] if score > 0]
        if not retrieved and scored:
            retrieved = [item for _, item in scored[:limit]]
    elif candidates:
        retrieved = candidates[:limit]
    else:
        behavioral = profile_store.load_behavioral(profile_id) or {
            "samples": (profile_store.load_raw(profile_id) or {}).get("samples", [])
        }
        samples = _sample_dicts(behavioral)
        if match_mode == "category" and situation and situation != "open":
            samples = [s for s in samples if str(s.get("category", "")).lower() == situation] or samples
        query = user_message.lower().strip()
        kw_scored: list[tuple[int, dict[str, Any]]] = []
        for item in samples:
            text = f"{item.get('prompt', '')} {item.get('response', '')}".lower()
            score = sum(1 for word in query.split() if len(word) > 3 and word in text)
            kw_scored.append((score, item))
        kw_scored.sort(key=lambda x: x[0], reverse=True)
        if kw_scored and kw_scored[0][0] > 0:
            retrieved = [
                {
                    "id": f"sample-{i}",
                    "situation": str(item.get("category", "open")),
                    "summary": str(item.get("prompt", ""))[:120],
                    "exemplar_line": str(item.get("response", ""))[:200],
                    "source": "raw_sample",
                }
                for i, (_, item) in enumerate(kw_scored[:limit])
            ]
        else:
            retrieved = [
                {
                    "id": f"sample-{i}",
                    "situation": str(item.get("category", "open")),
                    "summary": str(item.get("prompt", ""))[:120],
                    "exemplar_line": str(item.get("response", ""))[:200],
                    "source": "raw_sample",
                }
                for i, item in enumerate(samples[:limit])
            ]

    exemplars = _match_voice_exemplars(yaml_profile, situation, limit=max(1, limit - len(retrieved)))
    combined = (retrieved + exemplars)[:limit]
    used = bool(combined)
    return combined, used
