"""Run long-chat judge across familiarity stack ablation flags."""

from __future__ import annotations

import argparse
import asyncio
import json
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

ABLATIONS: dict[str, dict[str, bool]] = {
    "A0_full": {},
    "A1_no_planner": {"no_planner": True},
    "A2_no_retrieval": {"no_retrieval": True},
    "A3_no_situation_modes": {"no_situation_modes": True},
    "A4_l1_replay": {"l1_replay": True},
    "A5_no_situation": {"no_situation": True},
}


async def _run_ablation(
    profile_id: str,
    *,
    ablation_id: str,
    turns: int,
    scenario_id: str | None,
) -> dict:
    flags = ABLATIONS[ablation_id]
    brain = create_brain()
    store = ProfileStore(settings.profiles_data_dir)
    profile = store.load_final_profile(profile_id)
    if profile is None:
        raise ValueError(f"profile_not_found:{profile_id}")

    history: list[dict[str, str]] = []
    turn_rows: list[dict] = []
    participant_reply = await generate_opening_participant_reply(brain, profile_id=profile_id)

    for turn_idx in range(turns):
        conversation_open = turn_idx == 0
        user_message = participant_reply if turn_idx > 0 or not conversation_open else ""
        reply, meta = await run_chat_agent(
            brain,
            store,
            message=user_message,
            condition="A",
            profile_id=profile_id,
            conversation_history=history,
            scenario_id=scenario_id,
            conversation_open=conversation_open,
            ablation_flags=flags,
        )
        clean_reply = strip_roleplay_markers(reply)
        judged = await judge_profile_response(
            brain,
            profile=profile,
            prompt=user_message or "(conversation open)",
            agent_response=clean_reply,
        )
        turn_rows.append(
            {
                "turn": turn_idx + 1,
                "user": user_message,
                "assistant": clean_reply,
                "meta": meta,
                "judge": judged,
            }
        )
        history.append({"role": "user", "content": user_message or "(open)"})
        history.append({"role": "assistant", "content": clean_reply})
        if turn_idx + 1 < turns:
            participant_reply = await generate_participant_reply(
                brain,
                profile_id=profile_id,
                history=history,
                buddy_last_reply=clean_reply,
            )

    score_keys = list((turn_rows[0]["judge"]["scores"] if turn_rows else {}).keys())
    means = {
        key: sum(t["judge"]["scores"].get(key, 0) for t in turn_rows) / max(len(turn_rows), 1)
        for key in score_keys
    }
    retrieval_rate = sum(1 for t in turn_rows if t["meta"].get("retrieval_used")) / max(len(turn_rows), 1)
    return {
        "ablation_id": ablation_id,
        "ablation_flags": flags,
        "profile_id": profile_id,
        "turns": len(turn_rows),
        "means": means,
        "retrieval_rate": retrieval_rate,
        "turns_detail": turn_rows,
    }


async def main() -> None:
    parser = argparse.ArgumentParser(description="Familiarity stack ablation runner")
    parser.add_argument("profile_id", help="Profile to evaluate")
    parser.add_argument("--turns", type=int, default=10)
    parser.add_argument("--scenario", default=None)
    parser.add_argument(
        "--ablation",
        choices=list(ABLATIONS.keys()) + ["all"],
        default="all",
    )
    args = parser.parse_args()

    targets = list(ABLATIONS.keys()) if args.ablation == "all" else [args.ablation]
    results: list[dict] = []
    for ablation_id in targets:
        print(f"Running {ablation_id}...", file=sys.stderr)
        results.append(
            await _run_ablation(
                args.profile_id,
                ablation_id=ablation_id,
                turns=args.turns,
                scenario_id=args.scenario,
            )
        )

    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    out_dir = Path(settings.profiles_data_dir).parent / "evaluations"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{args.profile_id}_ablation_{stamp}.json"
    payload = {"profile_id": args.profile_id, "results": results}
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"ok": True, "path": str(out_path), "ablations": len(results)}, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
