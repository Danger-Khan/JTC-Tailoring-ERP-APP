"""Compatibility shim -- the real configuration lives in <root>/config.py.

Start.bat runs `cd app && pythonw main_gui.py`, which puts app/ at the head
of sys.path, so a `from config import Config` inside app/utils/*.py finds
THIS file rather than the one at the project root. This used to be a second
independent copy of that file, and since both derived their paths from
__file__, the two disagreed about DATA_DIR -- <root>/app/data here versus
<root>/data there. Which one you got was decided by the launcher, not by the
code.

Loading the root module by absolute path (under a private name, so it cannot
collide with whichever spelling of `config` is already in sys.modules) and
re-exporting Config makes both import paths hand back the same class object.
"""
import importlib.util
import os
import sys

_ROOT_CONFIG = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config.py")

_PRIVATE_NAME = "_jtc_root_config"

def _already_loaded():
    """Find the root module if some other import path got there first.

    A process that put the project root on sys.path imports it as plain
    `config`; if that process then also touches `app.config`, re-executing
    the file would give us a second Config class -- and a second read of the
    signing key -- describing the same settings. Reuse what is there.
    """
    for name in (_PRIVATE_NAME, "config"):
        mod = sys.modules.get(name)
        found = getattr(mod, "__file__", None)
        if found and os.path.abspath(found) == os.path.abspath(_ROOT_CONFIG):
            return mod
    return None


_module = _already_loaded()
if _module is None:
    if not os.path.exists(_ROOT_CONFIG):
        raise ImportError(
            "The project's configuration module is missing: %s. app/config.py "
            "is only a shim and has no settings of its own." % _ROOT_CONFIG)
    _spec = importlib.util.spec_from_file_location(_PRIVATE_NAME, _ROOT_CONFIG)
    _module = importlib.util.module_from_spec(_spec)
    # Registered before exec_module so a circular import resolves to the
    # partially-built module instead of executing the file a second time.
    sys.modules[_PRIVATE_NAME] = _module
    _spec.loader.exec_module(_module)

Config = _module.Config
