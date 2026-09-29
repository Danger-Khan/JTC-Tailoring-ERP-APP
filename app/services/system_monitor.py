"""Optional local-machine health probe for the shop counter PC.

Answers the questions an owner actually asks when something feels wrong:
is the internet up, is the machine short on memory, is the disk filling up.
CPU/RAM/disk come from psutil; the GPU is best-effort because there is no
portable way to read one.

Two rules shape the whole module:

- **It must never cost anything when switched off.** Nothing here runs
  unless the feature is enabled in Settings, and every probe is memoized so
  a 1-second UI refresh does not turn into a 1-second `nvidia-smi` fork.
- **It must never raise.** A health readout that crashes the till is worse
  than no readout, so every probe degrades to None and `snapshot()` always
  returns a full dict.

psutil is listed in requirements.txt, but the import is still guarded: a
missing optional dependency should grey out one card, not stop the app.
"""
import shutil
import socket
import subprocess
import sys

try:
    import psutil
except ImportError:  # pragma: no cover - exercised by the degraded path
    psutil = None
else:
    # Prime the CPU counter. psutil.cpu_percent(interval=None) reports load
    # since the PREVIOUS call, so the very first one always returns 0.0 --
    # and 0% is exactly what a broken readout looks like. Calling it once
    # here means the first reading the sidebar shows is a real measurement
    # of the time since the app started, not a placeholder.
    try:
        psutil.cpu_percent(interval=None)
    except Exception:  # pragma: no cover - a probe must never break import
        pass

try:
    from utils.performance import memoize_with_ttl
except ImportError:  # pragma: no cover - import style differs by entry point
    from app.utils.performance import memoize_with_ttl


# Probing DNS rather than fetching a page: it is one UDP-port TCP handshake
# to a well-known resolver, needs no HTTP stack, and does not depend on some
# third party's uptime. 1.1.1.1 and 8.8.8.8 are tried in turn so one
# operator having a bad day does not read as "the shop is offline".
_PROBE_HOSTS = (("1.1.1.1", 53), ("8.8.8.8", 53))


@memoize_with_ttl(ttl_seconds=10)
def internet_available(timeout=1.2):
    """True if a TCP connection to a public resolver succeeds.

    Cached for 10s: this is the one probe that can block, and blocking the
    Tk main loop for over a second every refresh would visibly stutter the
    clock.
    """
    for host, port in _PROBE_HOSTS:
        try:
            with socket.create_connection((host, port), timeout=timeout):
                return True
        except OSError:
            continue
    return False


# Long enough for a meaningful sample, short enough that a caller on the
# main thread (the smoke test) does not notice.
_CPU_SAMPLE_SECONDS = 0.12


@memoize_with_ttl(ttl_seconds=3)
def cpu_percent():
    """Whole-machine CPU load, or None if psutil is missing.

    Samples a real window rather than passing interval=None. Non-blocking
    was the original choice, but it reports load since the PREVIOUS call, so
    the first reading is always 0.0 and every later one depends on how long
    ago the cache happened to expire -- on an idle shop PC that showed a
    steady "0%", which is indistinguishable from a broken readout.

    Blocking here is safe because the only caller is snapshot(), and the GUI
    runs that on a worker thread precisely so it can afford to wait.
    """
    if psutil is None:
        return None
    try:
        return float(psutil.cpu_percent(interval=_CPU_SAMPLE_SECONDS))
    except Exception:
        return None


@memoize_with_ttl(ttl_seconds=3)
def memory_info():
    """(used_gb, total_gb, percent) or None."""
    if psutil is None:
        return None
    try:
        vm = psutil.virtual_memory()
        gb = 1024.0 ** 3
        return (round(vm.used / gb, 1), round(vm.total / gb, 1), float(vm.percent))
    except Exception:
        return None


@memoize_with_ttl(ttl_seconds=30)
def disk_info(path=None):
    """(used_gb, total_gb, percent) for the volume holding the data, or None.

    Defaults to the drive this app is installed on, because that is where
    the workbooks and the finance ledger live -- a full system drive is what
    would actually stop the shop working.
    """
    try:
        target = path or sys.prefix
        usage = shutil.disk_usage(target)
        gb = 1024.0 ** 3
        percent = (usage.used / usage.total * 100.0) if usage.total else 0.0
        return (round(usage.used / gb, 1), round(usage.total / gb, 1), round(percent, 1))
    except Exception:
        return None


@memoize_with_ttl(ttl_seconds=60)
def gpu_info():
    """GPU name and load, or None when there is no readable GPU.

    There is no portable GPU API, so this shells out to nvidia-smi and gives
    up quietly on anything else -- no NVIDIA card, no driver, an AMD or Intel
    part, a locked-down machine. Cached for a full minute and capped with a
    timeout, because forking a process is far more expensive than any other
    probe here.
    """
    try:
        out = subprocess.run(
            ["nvidia-smi",
             "--query-gpu=name,utilization.gpu,memory.used,memory.total",
             "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=2.5,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except (OSError, subprocess.SubprocessError):
        return None
    if out.returncode != 0 or not out.stdout.strip():
        return None
    try:
        name, util, used, total = [p.strip() for p in
                                   out.stdout.strip().splitlines()[0].split(",")][:4]
        return {"name": name, "load": float(util),
                "used_mb": float(used), "total_mb": float(total)}
    except (ValueError, IndexError):
        return None


def snapshot():
    """Everything the panel shows, in one call.

    Always returns every key. A probe that could not answer reports None,
    and the UI renders that as a dash rather than hiding the row -- an
    absent reading is information too.
    """
    return {
        "internet": internet_available(),
        "cpu": cpu_percent(),
        "memory": memory_info(),
        "disk": disk_info(),
        "gpu": gpu_info(),
        "psutil": psutil is not None,
    }
