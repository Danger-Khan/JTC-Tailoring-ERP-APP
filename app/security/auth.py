import bcrypt
from functools import wraps
from flask import g, request, jsonify, session
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from config import Config

# How long a bearer token stays valid. Tokens are stateless -- there is no
# server-side list to revoke from -- so this is the only thing limiting a
# leaked one, and a shop terminal does not need a long-lived credential.
TOKEN_MAX_AGE = 12 * 60 * 60  # seconds

def hash_password(password: str) -> str:
    """Hashes a plaintext password using bcrypt."""
    if not password:
        return ""
    if isinstance(password, str):
        password = password.encode('utf-8')
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password, salt).decode('utf-8')

def check_password(password: str, hashed_password: str) -> bool:
    """Verifies a plaintext password against a bcrypt hash."""
    if not password or not hashed_password:
        return False
    if isinstance(password, str):
        password = password.encode('utf-8')
    if isinstance(hashed_password, str):
        hashed_password = hashed_password.encode('utf-8')
    try:
        return bcrypt.checkpw(password, hashed_password)
    except Exception:
        return False

def _serializer():
    # Salted so a token cannot be swapped in for any other value signed with
    # the same SECRET_KEY (the session cookie, a future reset link).
    return URLSafeTimedSerializer(Config.SECRET_KEY, salt="jtc-auth-token")


def issue_token(user_id, username, role) -> str:
    """Signs the caller's identity into a bearer token."""
    return _serializer().dumps({
        "id": str(user_id),
        "username": str(username),
        "role": str(role),
    })


def verify_token(token):
    """Returns the identity carried by a valid token, otherwise None.

    This used to be `return {...Administrator...} if token else None`: any
    non-empty string -- "x", "null", a stale token, a guess -- authenticated
    as an administrator, which defeated @requires_auth on all twenty of the
    protected routes. The signature check below is the whole point of the
    decorator, so keep the failure closed: anything that does not verify,
    verifies as nobody.
    """
    if not token or not isinstance(token, str):
        return None
    try:
        data = _serializer().loads(token, max_age=TOKEN_MAX_AGE)
    except (BadSignature, SignatureExpired):
        return None
    if not isinstance(data, dict) or not data.get("username"):
        return None
    return data

def current_user():
    """Whoever this request authenticated as -- cookie session or token."""
    user = getattr(g, 'current_user', None)
    if user:
        return user
    if session.get('username'):
        return {
            "id": session.get('user_id'),
            "username": session.get('username'),
            "role": session.get('role', 'Viewer'),
        }
    return None


def requires_auth(f):
    @wraps(f)
    def decorator(*args, **kwargs):
        # Check Flask session first
        if session.get('username'):
            return f(*args, **kwargs)

        auth_header = request.headers.get('Authorization')
        if not auth_header:
            return jsonify({"error": "Authorization required"}), 401

        token = auth_header.split(" ")[-1] if " " in auth_header else auth_header
        user = verify_token(token)
        if not user:
            return jsonify({"error": "Invalid or expired token"}), 401

        # Carry the verified identity forward so requires_role can see it.
        # Without this a token-authenticated administrator fell through to
        # requires_role's session lookup, defaulted to "Viewer" and got a 403
        # on every route that also checks a role.
        g.current_user = user
        return f(*args, **kwargs)
    return decorator

def requires_role(*allowed_roles):
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            user = current_user() or {}
            user_role = user.get('role') or 'Viewer'
            if user_role not in allowed_roles:
                return jsonify({"error": "Forbidden: Insufficient permissions"}), 403
            return f(*args, **kwargs)
        return wrapper
    return decorator