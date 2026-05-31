"""Quick smoke test for sqlite session upsert and stats."""
import gc
import os
import tempfile

from app.storage.sqlite_store import SQLiteExperimentStore


def main() -> None:
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    try:
        store = SQLiteExperimentStore(path)
        store.record_session_end(
            session_id="s-test",
            duration_sec=120,
            message_count=2,
            end_reason="timer",
            participant_id="p1",
            condition="A",
            order_group="B-A",
        )
        row = store.list_sessions(limit=1)[0]
        assert row["duration_sec"] == 120
        assert row["session_id"] == "s-test"

        store.record_session_start(
            session_id="s-empty",
            participant_id="p2",
            condition="B",
            order_group="A-B",
        )
        stats = store.stats()
        assert stats["sessions"] >= 2
        print("ok")
    finally:
        del store
        gc.collect()
        if os.path.exists(path):
            try:
                os.remove(path)
            except PermissionError:
                pass


if __name__ == "__main__":
    main()
