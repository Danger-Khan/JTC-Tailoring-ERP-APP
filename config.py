"""Single source of truth for paths and secrets.

There used to be two byte-identical copies of this file -- one here and one
in app/ -- and `from config import Config` picked up whichever copy the
launcher happened to put on sys.path first. Because BASE_DIR was derived
from __file__, the two copies disagreed about where DATA_DIR was: started
from the project root it meant <root>/data, started from app/ (which is what
Start.bat does, `cd app && pythonw main_gui.py`) it meant <root>/app/data.
The same import statement named two different directories depending on how
the process was launched. app/config.py is now a shim that re-exports this
module, so both spellings resolve to the one object below.

The two stores stay separate, deliberately:

    DATA_DIR          <root>/data       the Flask API's workbooks
    DESKTOP_DATA_DIR  <root>/app/data   the live shop data the Tkinter app owns

They are not interchangeable. Both define tables named customers, orders,
inventory and employees, and the columns differ in every one of them -- the
desktop's customers sheet is (id, name, phone, length, sleeve, shoulder...)
while the API's CustomerModel is (id, name, phone, chest, waist, length,
sleeves, created_at). Pointing the API at the desktop store would have it
write its own column set straight over live customer records, so
initialize_database() refuses to build tables in DESKTOP_DATA_DIR.

Set JTC_DATA_DIR to move the API store somewhere else -- that is the hook
tests use to keep their fixtures out of both real directories.
"""
import os
import secrets


class Config:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

    # The API's own store. Overridable so tests never have to write into a
    # real data directory to exercise the Flask layer.
    DATA_DIR = os.environ.get('JTC_DATA_DIR') or os.path.join(BASE_DIR, 'data')

    # The desktop app's store, named here so code can *check against* it.
    # main_gui.py reaches its data through excel_manager.py, which computes
    # this same path from its own __file__ and never consults Config.
    DESKTOP_DATA_DIR = os.path.join(BASE_DIR, 'app', 'data')

    BACKUP_DIR = os.path.join(DATA_DIR, 'backups')
    UPLOAD_DIR = os.path.join(DATA_DIR, 'uploads')

    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16 MB upload limit
    ALLOWED_EXTENSIONS = {'.xlsx', '.xls', '.csv', '.txt', '.json'}

    # Session cookies and auth tokens are both signed with this. It used to
    # default to a literal checked into the repo, which means anyone holding
    # a copy of the source could forge either one. There is no safe constant
    # to ship, so absent SECRET_KEY in the environment we generate a random
    # key once and keep it in the data directory (mode 0600, gitignored).
    SECRET_KEY = None  # set by _load_secret_key() below

    @classmethod
    def ensure_dirs(cls):
        for d in (cls.DATA_DIR, cls.BACKUP_DIR, cls.UPLOAD_DIR):
            os.makedirs(d, exist_ok=True)


def _load_secret_key():
    """Environment first, then a generated key persisted beside the data.

    Persisting matters: a key regenerated per process would invalidate every
    session cookie and every outstanding auth token on each restart.
    """
    from_env = os.environ.get('SECRET_KEY')
    if from_env:
        return from_env

    key_path = os.path.join(Config.DATA_DIR, '.secret_key')
    try:
        with open(key_path, 'r', encoding='utf-8') as fh:
            existing = fh.read().strip()
        if existing:
            return existing
    except OSError:
        pass

    generated = secrets.token_urlsafe(48)
    try:
        with open(key_path, 'w', encoding='utf-8') as fh:
            fh.write(generated)
        os.chmod(key_path, 0o600)
    except OSError:
        # Read-only install: a per-process key still beats a published one.
        pass
    return generated


Config.ensure_dirs()
Config.SECRET_KEY = _load_secret_key()
