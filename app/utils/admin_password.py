"""Admin password storage for the desktop app.

The login used to compare against a literal `"admin123"` in the source. This
keeps that as the *factory* password but lets the owner set a real one, and
stores only a bcrypt hash of it.

Where the hash lives: the session cache next to the data
(`app/data/cache/app_state_cache.json`), because that is already the
per-install store and it travels with the shop's data rather than with the
code. An empty hash means "never changed" and the factory password still
works -- an existing install must keep opening after an update, not lock the
owner out of their own till.

Honest about what this is and is not: a bcrypt hash sitting beside the data
it guards stops someone reading the password over your shoulder or out of
the source. It does not stop someone who already has the machine and can
edit the JSON. The workbooks themselves are not encrypted, so the real
boundary here is physical access to the counter PC.
"""

try:
    import bcrypt
except ImportError:  # pragma: no cover - exercised by the degraded path
    bcrypt = None

# What the app ships with, and what an install that has never set a password
# keeps accepting.
FACTORY_PASSWORD = "admin123"

MIN_LENGTH = 4


def hashing_available():
    """False when bcrypt is missing, in which case changing the password is
    offered but refused rather than silently storing something weaker."""
    return bcrypt is not None


def hash_password(password):
    """bcrypt hash of a plaintext password, or "" if it cannot be made."""
    if not password or bcrypt is None:
        return ""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify(password, stored_hash):
    """Check a typed password against the stored hash.

    With no stored hash, falls back to the factory password. `bcrypt.checkpw`
    raises on a malformed hash -- a hand-edited or truncated cache file --
    and that must read as "wrong password", never as a crash on the login
    screen with no way past it.
    """
    if not password:
        return False
    if not stored_hash:
        return password == FACTORY_PASSWORD
    if bcrypt is None:
        # A hash was set on a machine that had bcrypt, and this one does not.
        # Refusing is the only safe answer: silently accepting the factory
        # password would undo the change the owner made.
        return False
    try:
        return bcrypt.checkpw(password.encode("utf-8"), stored_hash.encode("utf-8"))
    except (ValueError, TypeError):
        return False


def validate_new(new_password, confirm):
    """(ok, message) for a proposed new password. Message is a translation
    key so the dialog can show it in the active language."""
    if not new_password:
        return False, "pw_err_empty"
    if len(new_password) < MIN_LENGTH:
        return False, "pw_err_short"
    if new_password != confirm:
        return False, "pw_err_mismatch"
    if not hashing_available():
        return False, "pw_err_no_bcrypt"
    return True, ""


def is_factory_default(stored_hash):
    """True while the install is still on the shipped password, so the UI can
    nudge the owner to change it."""
    return not stored_hash
