import os
import importlib.util
import importlib
import sys
from datetime import datetime, timedelta, timezone
import zoneinfo

# deferred imports for claude_processor and blood_pressure_tracker are handled inside tests


def _make_fake_conn(capture):
    class FakeCursor:
        def execute(self, query, params=None):
            capture.append((query, params))

        def fetchone(self):
            return capture.pop(0) if capture else None

        def fetchall(self):
            return capture.pop(0) if capture else []

        def close(self):
            pass

    class FakeConn:
        def __init__(self):
            self._cursor = FakeCursor()

        def cursor(self):
            return self._cursor

        def commit(self):
            pass

        def close(self):
            pass

    return FakeConn()


def test_parse_to_utc_and_add_reading(monkeypatch):
    # Set required env vars before importing modules
    monkeypatch.setenv("TIMEZONE", "America/New_York")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "testkey")
    monkeypatch.setenv("PGPASSWORD", "REDACTED_PGPASSWORD")

    # Provide a ZoneInfo fallback for environments without tzdata
    def _fake_zoneinfo(key: str):
        if key == "UTC":
            return timezone.utc
        if key == "America/New_York":
            return timezone(timedelta(hours=-5))
        return timezone.utc

    monkeypatch.setattr(zoneinfo, "ZoneInfo", _fake_zoneinfo)

    # Capture execute params
    executed = []

    def fake_connect(**_kwargs):
        return _make_fake_conn(executed)

    import psycopg2

    monkeypatch.setattr(psycopg2, "connect", fake_connect)

    # Import modules after monkeypatching -- load by path to avoid pytest import issues
    base = os.getcwd()
    spec_bp = importlib.util.spec_from_file_location("blood_pressure_tracker", os.path.join(base, "blood_pressure_tracker.py"))
    bp = importlib.util.module_from_spec(spec_bp)
    spec_bp.loader.exec_module(bp)  # type: ignore
    # Make the module importable by name for modules that import it
    sys.modules["blood_pressure_tracker"] = bp

    # Provide a lightweight stub for ClaudeProcessor so bp_flask_app imports cleanly
    import types

    claude_mod = types.ModuleType("claude_processor")

    class _DummyClaude:
        def __init__(self, *a, **k):
            pass

    claude_mod.ClaudeProcessor = _DummyClaude
    sys.modules["claude_processor"] = claude_mod
    # Ensure bp_flask_utils is importable for bp_flask_app
    spec_utils = importlib.util.spec_from_file_location("bp_flask_utils", os.path.join(base, "bp_flask_utils.py"))
    utils_mod = importlib.util.module_from_spec(spec_utils)
    spec_utils.loader.exec_module(utils_mod)  # type: ignore
    sys.modules["bp_flask_utils"] = utils_mod

    spec_app = importlib.util.spec_from_file_location("bp_flask_app", os.path.join(base, "bp_flask_app.py"))
    app_mod = importlib.util.module_from_spec(spec_app)
    spec_app.loader.exec_module(app_mod)  # type: ignore

    # Test parse_to_utc helper
    dt_utc = app_mod.parse_to_utc("2025-12-12 08:15:58")
    assert dt_utc.tzinfo is not None
    # 08:15 EST is 13:15 UTC (EST = UTC-5)
    assert dt_utc.hour == 13 and dt_utc.minute == 15

    # Test add_reading stores a UTC datetime in execute params
    tracker = bp.BloodPressureTracker()
    tracker.add_reading(120, 80, None, "2025-12-12 08:15:58")

    # The last execute recorded should contain the INSERT params
    assert executed, "No DB execute recorded"
    _, params = executed[-1]
    stored_dt = params[0]
    assert stored_dt.tzinfo is not None
    assert stored_dt.hour == 13


def test_get_reading_by_id_converts_to_site_tz(monkeypatch):
    monkeypatch.setenv("TIMEZONE", "America/New_York")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "testkey")
    monkeypatch.setenv("PGPASSWORD", "REDACTED_PGPASSWORD")

    # Provide ZoneInfo fallback
    def _fake_zoneinfo(key: str):
        if key == "UTC":
            return timezone.utc
        if key == "America/New_York":
            return timezone(timedelta(hours=-5))
        return timezone.utc

    monkeypatch.setattr(zoneinfo, "ZoneInfo", _fake_zoneinfo)

    # Build a row with UTC datetime
    utc_dt = datetime(2025, 12, 12, 13, 15, 58, tzinfo=zoneinfo.ZoneInfo("UTC"))
    row = (1, utc_dt, 120, 80, None)

    # Fake connect that returns a cursor whose fetchone returns our row
    class Cursor:
        def __init__(self):
            self._returned = row

        def execute(self, *_a, **_k):
            pass

        def fetchone(self):
            return self._returned

        def close(self):
            pass

    class Conn:
        def cursor(self):
            return Cursor()

        def close(self):
            pass
        def commit(self):
            pass

    import psycopg2

    monkeypatch.setattr(psycopg2, "connect", lambda **kw: Conn())

    base = os.getcwd()
    # Provide a lightweight stub for ClaudeProcessor so bp_flask_app imports cleanly
    import types

    claude_mod = types.ModuleType("claude_processor")

    class _DummyClaude:
        def __init__(self, *a, **k):
            pass

    claude_mod.ClaudeProcessor = _DummyClaude
    sys.modules["claude_processor"] = claude_mod

    # Ensure bp_flask_utils is importable for bp_flask_app
    spec_utils = importlib.util.spec_from_file_location("bp_flask_utils", os.path.join(base, "bp_flask_utils.py"))
    utils_mod = importlib.util.module_from_spec(spec_utils)
    spec_utils.loader.exec_module(utils_mod)  # type: ignore
    sys.modules["bp_flask_utils"] = utils_mod

    spec_app = importlib.util.spec_from_file_location("bp_flask_app", os.path.join(base, "bp_flask_app.py"))
    app_mod = importlib.util.module_from_spec(spec_app)
    spec_app.loader.exec_module(app_mod)  # type: ignore

    reading = app_mod.get_reading_by_id(1)
    assert reading is not None
    # Should be converted to America/New_York (08:15)
    assert reading["date"].startswith("2025-12-12 08:15:58")
