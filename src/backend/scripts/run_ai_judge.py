"""Run the AI judge against a profile (generate sample + score + optional finalize)."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys

from app.agents.validation_graph import run_validation_ai_judge, run_validation_auto_test
from app.brain.factory import create_brain
from app.config import settings
from app.profiles.store import ProfileStore


async def _main() -> int:
    parser = argparse.ArgumentParser(description="AI judge for profile validation testing")
    parser.add_argument("profile_id", help="Behavioral profile id to evaluate")
    parser.add_argument("--samples", type=int, default=1, help="Number of generate+judge rounds")
    parser.add_argument("--finalize", action="store_true", help="Aggregate scores and save validation")
    parser.add_argument("--prompt", default="", help="Optional user prompt (skip generate)")
    parser.add_argument("--response", default="", help="Optional agent reply to score")
    args = parser.parse_args()

    store = ProfileStore(settings.profiles_data_dir)
    brain = create_brain()

    if args.prompt and args.response:
        result = await run_validation_ai_judge(
            brain,
            store,
            profile_id=args.profile_id,
            prompt=args.prompt,
            agent_response=args.response,
            generate_if_missing=False,
        )
    else:
        result = await run_validation_auto_test(
            brain,
            store,
            profile_id=args.profile_id,
            samples=args.samples,
            finalize=args.finalize,
        )

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(_main()))
