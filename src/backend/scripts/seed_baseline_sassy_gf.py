"""Install the committed baseline_sassy_gf test profile into data/profiles/."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import yaml

from app.config import settings
from app.profiles.store import ProfileStore
from app.profiles.yaml_profile import dump_profile_yaml, normalize_profile_yaml

ROOT = Path(__file__).resolve().parents[1]
SOURCE_YAML = ROOT / "profiles" / "baseline_sassy_gf.yaml"
SOURCE_RAW = ROOT / "profiles" / "baseline_sassy_gf.raw.json"


def main() -> int:
    if not SOURCE_YAML.is_file() or not SOURCE_RAW.is_file():
        print("missing baseline source files in profiles/", file=sys.stderr)
        return 1

    profile = normalize_profile_yaml(yaml.safe_load(SOURCE_YAML.read_text(encoding="utf-8")))
    raw = json.loads(SOURCE_RAW.read_text(encoding="utf-8"))

    store = ProfileStore(settings.profiles_data_dir)
    store.save_raw(raw)
    saved = store.save_behavioral_yaml(profile)

    moments: list[dict] = []
    for idx, ex in enumerate(profile.get("voice_exemplars") or [], start=1):
        if not isinstance(ex, dict):
            continue
        line = str(ex.get("line", "")).strip()
        if not line:
            continue
        context = str(ex.get("context", "open"))
        moments.append(
            {
                "id": f"m-ex-{idx:03d}",
                "situation": context,
                "summary": f"Voice exemplar for {context}",
                "exemplar_line": line,
                "prompt": "",
                "response": line,
                "source_turn": idx,
            }
        )
    for idx, sample in enumerate(raw.get("samples") or [], start=1):
        if not isinstance(sample, dict):
            continue
        response = str(sample.get("response", "")).strip()
        if not response:
            continue
        moments.append(
            {
                "id": f"m-sample-{idx:03d}",
                "situation": str(sample.get("category", "open")),
                "summary": str(sample.get("prompt", ""))[:120],
                "exemplar_line": response[:300],
                "prompt": str(sample.get("prompt", ""))[:300],
                "response": response[:300],
                "source_turn": len(moments) + 1,
            }
        )
    store.save_moments(
        {
            "profile_id": profile["profile_id"],
            "moments": moments,
            "moment_count": len(moments),
        }
    )

    print(json.dumps(
        {
            "ok": True,
            "profile_id": saved.get("profile_id"),
            "yaml": str(store.behavioral_dir / f"{profile['profile_id']}.yaml"),
            "raw": str(store.raw_dir / f"{profile['profile_id']}.json"),
            "sample_count": len(raw.get("samples") or []),
            "moment_count": len(moments),
        },
        ensure_ascii=False,
        indent=2,
    ))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
