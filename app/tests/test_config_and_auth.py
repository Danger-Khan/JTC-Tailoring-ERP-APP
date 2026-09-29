"""The configuration and API-auth defects found in the full-codebase audit.

Three separate bugs, all of which looked fine from the outside:

  * `from config import Config` resolved to one of two identical-looking
    files depending on how the process was started, and the two disagreed
    about which directory held the data.
  * initialize_database() created workbooks with no header row, which every
    reader and writer in excel_db.py silently mis-handles.
  * verify_token() authenticated any non-empty string as an administrator.

These run without a live server; the decorator tests build a throwaway Flask
app rather than create_app(), so nothing here needs a data directory.
"""
import importlib.util
import os
import sys
import tempfile
import unittest

import openpyxl
from flask import Flask, jsonify

from app.security import auth
from app.utils import excel_db

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


class ConfigResolutionTestCase(unittest.TestCase):
    """app/config.py used to be a second copy of the root config, and which
    one an import got was decided by sys.path, not by the code."""

    def test_both_spellings_name_the_same_settings(self):
        from app.config import Config as viaapp
        from config import Config as viaroot
        self.assertIs(viaroot, viaapp)
        self.assertEqual(viaroot.DATA_DIR, viaapp.DATA_DIR)

    def test_app_config_is_a_shim_with_no_settings_of_its_own(self):
        """Loaded standalone -- as Start.bat's `cd app` arranges -- it must
        still hand back the root module's Config rather than defining one."""
        source = open(os.path.join(ROOT, "app", "config.py"), encoding="utf-8").read()
        self.assertNotIn("class Config", source,
                         "app/config.py has grown its own Config again")
        shim = _load("_shim_probe", os.path.join(ROOT, "app", "config.py"))
        root = _load("_root_probe", os.path.join(ROOT, "config.py"))
        self.assertEqual(shim.Config.DATA_DIR, root.Config.DATA_DIR)

    def test_the_two_stores_are_not_the_same_directory(self):
        """Both sides define customers/orders/inventory/employees with
        different columns; sharing a directory would overwrite live data."""
        from config import Config
        self.assertNotEqual(os.path.abspath(Config.DATA_DIR),
                            os.path.abspath(Config.DESKTOP_DATA_DIR))

    def test_secret_key_is_not_a_shipped_constant(self):
        """It signs session cookies and auth tokens. The old default was a
        literal in the repo, so anyone with the source could forge both."""
        from config import Config
        self.assertNotIn("atelier", Config.SECRET_KEY.lower())
        self.assertNotIn("change-in-production", Config.SECRET_KEY)
        self.assertGreaterEqual(len(Config.SECRET_KEY), 32)

    def test_data_dir_honours_the_environment_override(self):
        """conftest.py relies on this to keep the suite off the real store."""
        from config import Config
        self.assertEqual(os.path.abspath(Config.DATA_DIR),
                         os.path.abspath(os.environ["JTC_DATA_DIR"]))


class InitializeDatabaseTestCase(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="jtc-init-")
        self._saved = (excel_db.Config.DATA_DIR, excel_db.Config.BACKUP_DIR)
        excel_db.Config.DATA_DIR = self.tmp
        excel_db.Config.BACKUP_DIR = os.path.join(self.tmp, "backups")
        os.makedirs(excel_db.Config.BACKUP_DIR, exist_ok=True)

    def tearDown(self):
        excel_db.Config.DATA_DIR, excel_db.Config.BACKUP_DIR = self._saved

    def _headers(self, table):
        path = os.path.join(self.tmp, "%s.xlsx" % table)
        return [c.value for c in openpyxl.load_workbook(path).active[1]]

    def test_every_table_gets_a_header_row(self):
        excel_db.initialize_database()
        for table, expected in excel_db.TABLE_SCHEMAS.items():
            self.assertEqual(self._headers(table), expected,
                             "%s has the wrong row 1" % table)

    def test_headers_land_in_row_one(self):
        """sheet.append() on a loaded empty workbook writes row 2, leaving
        row 1 blank -- and row 1 is what every reader here looks at."""
        excel_db.initialize_database()
        sheet = openpyxl.load_workbook(os.path.join(self.tmp, "users.xlsx")).active
        self.assertEqual(sheet.max_row, 1)
        self.assertEqual(sheet.cell(row=1, column=1).value, "id")

    def test_a_headerless_workbook_is_repaired(self):
        path = os.path.join(self.tmp, "users.xlsx")
        openpyxl.Workbook().save(path)  # exactly what the old code produced
        excel_db.initialize_database()
        self.assertEqual(self._headers("users"), excel_db.TABLE_SCHEMAS["users"])

    def test_an_existing_header_row_is_left_alone(self):
        """Even one whose columns differ -- reshaping data is not this
        function's job, and the desktop's sheets share these table names."""
        path = os.path.join(self.tmp, "customers.xlsx")
        wb = openpyxl.Workbook()
        wb.active.append(["id", "name", "phone", "length", "sleeve"])
        wb.active.append(["C-1", "Farman", "0300", "40", "24"])
        wb.save(path)
        excel_db.initialize_database()
        self.assertEqual(self._headers("customers"),
                         ["id", "name", "phone", "length", "sleeve"])
        rows = list(openpyxl.load_workbook(path).active.iter_rows(values_only=True))
        self.assertEqual(rows[1][1], "Farman")

    def test_it_refuses_to_build_tables_in_the_desktop_store(self):
        excel_db.Config.DATA_DIR = excel_db.Config.DESKTOP_DATA_DIR
        with self.assertRaises(RuntimeError) as caught:
            excel_db.initialize_database()
        self.assertIn("desktop", str(caught.exception).lower())

    def test_records_saved_into_a_headerless_sheet_keep_their_values(self):
        """The regression this all hangs off: the old repair path put the
        headers in row 2, so the field mapping read row 1 (all None) and
        every record was stored as a row of empty strings."""
        path = os.path.join(self.tmp, "users.xlsx")
        openpyxl.Workbook().save(path)
        db = excel_db.ExcelDB("users")
        db.save_record({"id": "USR-101", "username": "amir", "role": "Tailor"})
        rows = db.get_all()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["username"], "amir")
        self.assertEqual(rows[0]["role"], "Tailor")


class TokenTestCase(unittest.TestCase):

    def test_a_freshly_issued_token_verifies(self):
        user = auth.verify_token(auth.issue_token("USR-101", "amir", "Administrator"))
        self.assertIsNotNone(user)
        self.assertEqual(user["username"], "amir")
        self.assertEqual(user["role"], "Administrator")

    def test_an_arbitrary_string_is_not_a_token(self):
        """`return {...} if token else None` accepted every one of these."""
        for junk in ("x", "null", "Bearer", "undefined", "admin",
                     "eyJhbGciOiJIUzI1NiJ9.e30.x", " "):
            self.assertIsNone(auth.verify_token(junk), "accepted %r" % junk)

    def test_empty_and_non_string_values_are_rejected(self):
        for junk in ("", None, 0, [], {}, b"token"):
            self.assertIsNone(auth.verify_token(junk), "accepted %r" % junk)

    def test_a_tampered_payload_is_rejected(self):
        """Promote yourself to Administrator in the payload and keep the
        signature that was issued for a Viewer."""
        from itsdangerous.encoding import base64_decode, base64_encode
        token = auth.issue_token("USR-9", "viewer", "Viewer")
        payload, timestamp, signature = token.split(".")
        # Same length, so the JSON stays well-formed without re-signing.
        claim = base64_decode(payload).replace(b'"Viewer"', b'"Admin1"')
        forged = ".".join([base64_encode(claim).decode(), timestamp, signature])
        self.assertNotEqual(forged, token, "the payload was not actually changed")
        self.assertIsNone(auth.verify_token(forged))

    def test_a_token_signed_with_another_key_is_rejected(self):
        from itsdangerous import URLSafeTimedSerializer
        other = URLSafeTimedSerializer("a-different-secret", salt="jtc-auth-token")
        forged = other.dumps({"id": "1", "username": "mallory", "role": "Administrator"})
        self.assertIsNone(auth.verify_token(forged))

    def test_a_token_signed_under_a_different_salt_is_rejected(self):
        from itsdangerous import URLSafeTimedSerializer
        from config import Config
        other = URLSafeTimedSerializer(Config.SECRET_KEY, salt="some-other-purpose")
        forged = other.dumps({"id": "1", "username": "mallory", "role": "Administrator"})
        self.assertIsNone(auth.verify_token(forged))

    def test_an_expired_token_is_rejected(self):
        token = auth.issue_token("USR-101", "amir", "Administrator")
        saved = auth.TOKEN_MAX_AGE
        auth.TOKEN_MAX_AGE = -1
        try:
            self.assertIsNone(auth.verify_token(token))
        finally:
            auth.TOKEN_MAX_AGE = saved
        self.assertIsNotNone(auth.verify_token(token), "restore failed")


class ProtectedRouteTestCase(unittest.TestCase):
    """The decorators as a route actually meets them."""

    def setUp(self):
        from config import Config
        app = Flask(__name__)
        app.config["SECRET_KEY"] = Config.SECRET_KEY

        @app.route("/guarded")
        @auth.requires_auth
        def guarded():
            return jsonify({"ok": True})

        @app.route("/admin-only")
        @auth.requires_auth
        @auth.requires_role("Administrator")
        def admin_only():
            return jsonify({"ok": True})

        self.client = app.test_client()

    def test_no_header_is_rejected(self):
        self.assertEqual(self.client.get("/guarded").status_code, 401)

    def test_a_guessed_bearer_token_is_rejected(self):
        response = self.client.get("/guarded", headers={"Authorization": "Bearer admin"})
        self.assertEqual(response.status_code, 401,
                         "any non-empty token used to authenticate as Administrator")

    def test_a_valid_token_is_accepted(self):
        token = auth.issue_token("USR-101", "amir", "Administrator")
        response = self.client.get("/guarded",
                                   headers={"Authorization": "Bearer %s" % token})
        self.assertEqual(response.status_code, 200)

    def test_a_token_carries_its_role_into_requires_role(self):
        """requires_role read the session only, so a token-authenticated
        administrator fell through to the 'Viewer' default and got a 403."""
        token = auth.issue_token("USR-101", "amir", "Administrator")
        response = self.client.get("/admin-only",
                                   headers={"Authorization": "Bearer %s" % token})
        self.assertEqual(response.status_code, 200)

    def test_a_token_cannot_claim_a_role_it_was_not_issued(self):
        token = auth.issue_token("USR-7", "viewer", "Viewer")
        response = self.client.get("/admin-only",
                                   headers={"Authorization": "Bearer %s" % token})
        self.assertEqual(response.status_code, 403)


if __name__ == "__main__":
    unittest.main()
