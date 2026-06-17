"""Run a multi-turn profile chat and score each Buddy reply with the AI judge."""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

from app.agents.ai_judge import judge_profile_response
from app.agents.conversation_agent import run_chat_agent
from app.agents.simulated_participant import (
    generate_opening_participant_reply,
    generate_participant_reply,
)
from app.brain.factory import create_brain
from app.config import settings
from app.pipeline.text_clean import strip_roleplay_markers
from app.profiles.store import ProfileStore

# Legacy scripted turns (ignores Buddy — use only with --scripted).
SCRIPTED_USER_MESSAGES: list[str] = [
    "Pues hoy estuvo tranquilo, trabajé un rato y ya estoy en casa.",
    "Después suelo poner música y descansar un rato en el sillón.",
    "Últimamente me ha gustado mucho cocinar cosas sencillas.",
    "¿Y tú qué sueles hacer cuando quieres desconectar?",
    "Ayer vi un capítulo de una serie y se me fue la tarde.",
    "Los trámites son un rollo, la verdad, pero hay que hacerlos.",
    "Oye, un amigo me contó que le ascendieron en el trabajo.",
    "Hoy se me olvidó el paraguas y llegué empapado al carro.",
    "¿Tienes alguna receta fácil para cuando no quieres complicarte?",
    "Tuve un día pesado, muchas reuniones seguidas.",
    "Jaja, mi hermano me mandó un meme buenísimo hace rato.",
    "¿Prefieres quedarte en casa o salir un rato?",
    "Estoy pensando en retomar algo que dejé hace tiempo.",
    "A veces me cuesta desconectar de la pantalla.",
    "¿Qué tipo de música te relaja?",
    "Mañana madrugo y no tengo ninguna ganas.",
    "Gracias por charlar un rato, se siente ligero.",
    "Bueno, ya me tengo que ir a preparar algo de cena.",
    "Fue bueno hablar contigo, en serio.",
    "Nos vemos, cuídate.",
]


def _clean_reply(text: str) -> str:
    body = strip_roleplay_markers(text)
    body = re.sub(r"<JSON>.*", "", body, flags=re.DOTALL).strip()
    return body


async def _buddy_reply(
    brain,
    store,
    *,
    profile_id: str,
    history: list[dict[str, str]],
    user_message: str,
    scenario_id: str | None,
    conversation_open: bool,
) -> tuple[str, dict]:
    reply, meta = await run_chat_agent(
        brain,
        store,
        message=user_message,
        condition="A",
        profile_id=profile_id,
        conversation_history=history,
        scenario_id=scenario_id,
        conversation_open=conversation_open,
    )
    return _clean_reply(reply), meta


async def _run(
    profile_id: str,
    *,
    scenario_id: str | None,
    min_turns: int,
    scripted: bool,
    fast: bool = False,
) -> dict:
    if fast:
        object.__setattr__(settings, "behavioral_planner_mode", "heuristic")
        object.__setattr__(settings, "situation_classifier_mode", "keyword")
        object.__setattr__(settings, "llm_num_predict", min(settings.llm_num_predict, 256))

    store = ProfileStore(settings.profiles_data_dir)
    brain = create_brain()
    profile = store.load_final_profile(profile_id)
    if profile is None:
        raise ValueError(f"profile_not_found:{profile_id}")

    history: list[dict[str, str]] = []
    transcript: list[dict] = []
    judgements: list[dict] = []
    participant_mode = "scripted" if scripted else "simulated"

    # Turn 1 — Buddy opens.
    buddy_text, meta = await _buddy_reply(
        brain,
        store,
        profile_id=profile_id,
        history=history,
        user_message="",
        scenario_id=scenario_id,
        conversation_open=True,
    )
    history.append({"role": "assistant", "content": buddy_text})
    judged = await judge_profile_response(
        brain,
        profile=profile,
        prompt="[Buddy abre la conversación]",
        agent_response=buddy_text,
    )
    transcript.append(
        {
            "turn": 1,
            "user": "",
            "assistant": buddy_text,
            "conversation_open": True,
            "participant_mode": participant_mode,
            "judge": judged,
            "metadata": meta,
        }
    )
    judgements.append(judged["scores"])

    scripted_queue = list(SCRIPTED_USER_MESSAGES)

    for turn in range(2, min_turns + 1):
        if scripted:
            if not scripted_queue:
                break
            user_text = scripted_queue.pop(0)
        else:
            if turn == 2:
                user_text = await generate_opening_participant_reply(
                    brain,
                    buddy_opening=buddy_text,
                    profile_store=store,
                    profile_id=profile_id,
                    total_turns=min_turns,
                )
            else:
                user_text = await generate_participant_reply(
                    brain,
                    buddy_last_message=history[-1]["content"],
                    conversation_history=history,
                    profile_store=store,
                    profile_id=profile_id,
                    turn_index=turn,
                    total_turns=min_turns,
                )

        buddy_text, meta = await _buddy_reply(
            brain,
            store,
            profile_id=profile_id,
            history=history,
            user_message=user_text,
            scenario_id=scenario_id,
            conversation_open=False,
        )
        history.append({"role": "user", "content": user_text})
        history.append({"role": "assistant", "content": buddy_text})

        judged = await judge_profile_response(
            brain,
            profile=profile,
            prompt=user_text,
            agent_response=buddy_text,
        )
        transcript.append(
            {
                "turn": turn,
                "user": user_text,
                "assistant": buddy_text,
                "conversation_open": False,
                "participant_mode": participant_mode,
                "judge": judged,
                "metadata": meta,
            }
        )
        judgements.append(judged["scores"])
        print(
            f"[turn {turn}/{min_turns}] participant=({participant_mode}) "
            f"naturalness={judged['scores'].get('naturalness')} "
            f"reminds={judged['scores'].get('reminds_me_of_person')}",
            flush=True,
        )

    def _mean(key: str) -> float:
        vals = [float(j.get(key, 0)) for j in judgements]
        return round(sum(vals) / max(len(vals), 1), 2)

    summary = {
        "turns": len(transcript),
        "participant_mode": participant_mode,
        "mean_tone_similarity": _mean("tone_similarity"),
        "mean_phrasing_similarity": _mean("phrasing_similarity"),
        "mean_behavioral_consistency": _mean("behavioral_consistency"),
        "mean_reminds_me_of_person": _mean("reminds_me_of_person"),
        "mean_naturalness": _mean("naturalness"),
        "mean_identity_leakage_absent": _mean("identity_leakage_absent"),
    }
    return {
        "profile_id": profile_id,
        "scenario_id": scenario_id or "daily_conversation",
        "participant_mode": participant_mode,
        "llm_model": settings.resolved_llm_model,
        "llm_provider": settings.llm_provider,
        "pipeline_fast": fast,
        "run_at": datetime.now(timezone.utc).isoformat(),
        "transcript": transcript,
        "summary": summary,
    }


def _format_markdown(report: dict) -> str:
    mode = report.get("participant_mode", "simulated")
    lines = [
        f"# Chat + AI judge — `{report['profile_id']}`",
        "",
        f"Scenario: **{report['scenario_id']}** | Turns: **{report['summary']['turns']}** | "
        f"Participant: **{mode}** | Model: **{report.get('llm_model', '?')}** | Run: {report['run_at']}",
        "",
        "## Summary (mean judge scores)",
        "",
        "| Metric | Mean |",
        "|--------|------|",
    ]
    for key, val in report["summary"].items():
        if key in {"turns", "participant_mode"}:
            continue
        lines.append(f"| {key} | {val} |")
    lines.extend(["", "---", ""])
    for item in report["transcript"]:
        turn = item["turn"]
        lines.append(f"### Turn {turn}")
        if item.get("conversation_open"):
            lines.append("*[Buddy opens the conversation]*")
        else:
            lines.append(f"**Participant:** {item['user']}")
        lines.append("")
        lines.append(f"**Buddy:** {item['assistant']}")
        scores = item["judge"]["scores"]
        rationale = item["judge"].get("rationale", "")
        lines.append("")
        lines.append(
            f"*Judge:* tone={scores.get('tone_similarity')} phrasing={scores.get('phrasing_similarity')} "
            f"consistency={scores.get('behavioral_consistency')} reminds={scores.get('reminds_me_of_person')} "
            f"naturalness={scores.get('naturalness')} identity_safe={scores.get('identity_leakage_absent')}"
        )
        if rationale:
            lines.append(f"*Rationale:* {rationale}")
        lines.append("")
    return "\n".join(lines)


async def _main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("profile_id", nargs="?", default="pf-20260610-0237")
    parser.add_argument("--turns", type=int, default=20, help="Number of interactions (default 20)")
    parser.add_argument("--scenario", default="daily_conversation")
    parser.add_argument("--scripted", action="store_true", help="Use legacy topic-list participant")
    parser.add_argument("--fast", action="store_true", help="Keyword classifier + heuristic planner (fewer LLM calls)")
    parser.add_argument("--out", default="", help="Output path (.json and .md)")
    args = parser.parse_args()

    turns = max(1, args.turns)
    try:
        report = await _run(
            args.profile_id,
            scenario_id=args.scenario,
            min_turns=turns,
            scripted=args.scripted,
            fast=args.fast,
        )
    except Exception as exc:  # noqa: BLE001
        print(f"failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1

    out_base = args.out.strip()
    if not out_base:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        suffix = "scripted" if args.scripted else "simulated"
        out_dir = Path(settings.profiles_data_dir).parent / "evaluations"
        out_dir.mkdir(parents=True, exist_ok=True)
        out_base = str(out_dir / f"{args.profile_id}_{suffix}_{stamp}")

    json_path = Path(f"{out_base}.json")
    md_path = Path(f"{out_base}.md")
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(_format_markdown(report), encoding="utf-8")

    print(json.dumps(report["summary"], ensure_ascii=False, indent=2))
    print(f"\nWrote {json_path}")
    print(f"Wrote {md_path}")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(_main()))
