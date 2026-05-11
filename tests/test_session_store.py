from app.session_store import MemorySessionStore, SQLiteSessionStore


def test_memory_session_roundtrip():
    store = MemorySessionStore()
    sid = store.create_session(r"GALAXY\ken", "pw")
    assert store.get_session_credentials(sid) == (r"GALAXY\ken", "pw")
    store.drop_session(sid)
    assert store.get_session_credentials(sid) is None


def test_sqlite_session_roundtrip(tmp_path):
    db = tmp_path / "sessions.db"
    store = SQLiteSessionStore(str(db), "unit-test-secret-key-32chars-minimum-xx")
    store.init_db()
    sid = store.create_session(r"DOMAIN\user", "s3cr3t")
    assert store.get_session_credentials(sid) == (r"DOMAIN\user", "s3cr3t")
    store.drop_session(sid)
    assert store.get_session_credentials(sid) is None
