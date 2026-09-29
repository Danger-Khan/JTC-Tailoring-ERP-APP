"""Every dependency requirements.txt declares must actually be importable.

Written because psutil was listed in requirements.txt and not installed in
the virtualenv, so the machine-health strip in the sidebar showed a dash for
CPU and RAM. Nothing failed, nothing logged, and no test noticed -- the
import is deliberately guarded so a missing optional dependency greys out
one card instead of stopping the app, which is right for the shop and
useless for catching this.

The guard protects the user. This protects the developer.
"""
import importlib
import os
import re
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
REQUIREMENTS = os.path.join(ROOT, "requirements.txt")

# Distribution name -> module name, where they differ.
IMPORT_NAMES = {
    "pillow": "PIL",
    "flask-cors": "flask_cors",
    "python-bidi": "bidi",
    "arabic-reshaper": "arabic_reshaper",
}


def _declared():
    """(distribution, requirement line) for each real requirement."""
    out = []
    with open(REQUIREMENTS, encoding="utf-8") as handle:
        for raw in handle:
            line = raw.split("#", 1)[0].strip()
            if not line or line.startswith("-"):
                continue
            name = re.split(r"[<>=!~\[]", line, 1)[0].strip()
            if name:
                out.append((name.lower(), line))
    return out


class RequirementsTestCase(unittest.TestCase):

    def test_requirements_file_is_readable_and_not_empty(self):
        self.assertTrue(os.path.exists(REQUIREMENTS), REQUIREMENTS)
        self.assertGreater(len(_declared()), 0, "no requirements parsed")

    def test_every_declared_dependency_is_installed(self):
        missing = []
        for dist, line in _declared():
            module = IMPORT_NAMES.get(dist, dist.replace("-", "_"))
            try:
                importlib.import_module(module)
            except ImportError:
                missing.append("%s (import %s)" % (line, module))
        self.assertEqual(
            missing, [],
            "declared in requirements.txt but not importable:\n  "
            + "\n  ".join(missing)
            + "\n\nRun: .venv/Scripts/python.exe -m pip install -r requirements.txt")

    def test_psutil_specifically_is_present(self):
        """Named on its own because its absence is silent: system_monitor
        guards the import and reports None, so CPU and RAM quietly render
        as a dash instead of a number."""
        import importlib.util
        self.assertIsNotNone(importlib.util.find_spec("psutil"),
                             "the sidebar's CPU and RAM readouts need psutil")


class SystemMonitorTestCase(unittest.TestCase):
    """The probes themselves, against this machine."""

    def setUp(self):
        from app.services import system_monitor
        self.sysmon = system_monitor

    def test_snapshot_always_returns_every_key(self):
        snap = self.sysmon.snapshot()
        self.assertEqual(set(snap),
                         {"internet", "cpu", "memory", "disk", "gpu", "psutil"})

    def test_cpu_and_memory_report_real_numbers(self):
        self.assertTrue(self.sysmon.snapshot()["psutil"], "psutil not importable")

        cpu = self.sysmon.cpu_percent()
        self.assertIsNotNone(cpu, "CPU read as None with psutil present")
        self.assertGreaterEqual(cpu, 0.0)
        self.assertLessEqual(cpu, 100.0)

        mem = self.sysmon.memory_info()
        self.assertIsNotNone(mem, "RAM read as None with psutil present")
        used, total, pct = mem
        self.assertGreater(total, 0.0, "a machine with no RAM is not running this")
        self.assertLessEqual(used, total)
        self.assertGreaterEqual(pct, 0.0)
        self.assertLessEqual(pct, 100.0)

    def test_disk_reports_a_real_volume(self):
        disk = self.sysmon.disk_info()
        self.assertIsNotNone(disk)
        used, total, pct = disk
        self.assertGreater(total, 0.0)
        self.assertLessEqual(used, total)

    def test_the_gpu_probe_either_answers_fully_or_not_at_all(self):
        """Best-effort by design -- there is no portable GPU API, so a
        machine with no NVIDIA card reports None. What it must never do is
        return a half-filled dict the sidebar then formats into nonsense."""
        gpu = self.sysmon.gpu_info()
        if gpu is None:
            self.skipTest("no readable GPU on this machine")
        self.assertEqual(set(gpu), {"name", "load", "used_mb", "total_mb"})
        self.assertTrue(gpu["name"])
        self.assertGreaterEqual(gpu["load"], 0.0)
        self.assertGreater(gpu["total_mb"], 0.0, "a GPU with no memory is a bad reading")
        self.assertLessEqual(gpu["used_mb"], gpu["total_mb"])

    def test_probes_never_raise_even_without_psutil(self):
        """A health readout that crashes the till is worse than none."""
        saved = self.sysmon.psutil
        self.sysmon.psutil = None
        try:
            for probe in (self.sysmon.cpu_percent, self.sysmon.memory_info):
                probe.cache_clear()
                self.assertIsNone(probe())
            self.sysmon.snapshot()  # must not raise
        finally:
            self.sysmon.psutil = saved
            self.sysmon.cpu_percent.cache_clear()
            self.sysmon.memory_info.cache_clear()


if __name__ == "__main__":
    unittest.main()
