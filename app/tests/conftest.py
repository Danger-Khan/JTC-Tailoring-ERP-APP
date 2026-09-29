"""Keep the API-side tests out of the real data directory.

Config.DATA_DIR is resolved once, at import time, from JTC_DATA_DIR -- so the
redirect has to be in place before anything imports `config`. conftest.py is
loaded before any test module, which is the only hook early enough.

Without this, create_app() in test_suite.py runs initialize_database()
against <root>/data, i.e. the store a real server would be using.
"""
import os
import tempfile

_TMP = os.path.join(tempfile.gettempdir(), "jtc-erp-test-data")
os.makedirs(_TMP, exist_ok=True)
os.environ["JTC_DATA_DIR"] = _TMP
