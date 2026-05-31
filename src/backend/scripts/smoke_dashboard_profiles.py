"""Smoke test profile list/detail/delete used by the research dashboard."""
from __future__ import annotations

import tempfile

from app.profiles.store import ProfileStore


def main() -> None:
    d = tempfile.mkdtemp()
    store = ProfileStore(base_dir=d)
    store.save_raw(
        {
            "profile_id": "pf-test",
            "modeled_user_alias": "Luis",
            "samples": [{"prompt": "p", "response": "r"}],
        }
    )
    store.save_behavioral_yaml(
        {
            "profile_id": "pf-test",
            "profile_version": "1.0.0",
            "source": "t",
            "style": {"formality": "low"},
            "constraints": {},
        }
    )
    rows = store.list_profiles_detail()
    assert len(rows) == 1 and rows[0]["profile_id"] == "pf-test"
    detail = store.get_profile_detail("pf-test")
    assert detail is not None
    stats = store.profile_stats()
    assert stats["profiles"] == 1
    deleted = store.delete_profile("pf-test")
    assert sum(deleted.values()) >= 2
    assert store.get_profile_detail("pf-test") is None
    print("smoke_dashboard_profiles ok")


if __name__ == "__main__":
    main()
