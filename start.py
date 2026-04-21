"""
start.py — single-shell launcher for AXIOM-Body.

Spawns the three long-running processes that make up a live body:
  - ears/vision.py      (YOLO scene writer)
  - ears/listener.py    (Whisper VAD + transcribe)
  - face/face-engine.py (state machine; auto-spawns senses-server on 127.0.0.1:7899)

Streams each child's stdout to the parent with a prefix so one terminal shows
the whole body. Ctrl+C cleans up all children. No background-ness to track,
no zombie python.exe piling up.

Usage:
  python start.py                   # launch all three
  python start.py --no-listener     # skip the mic (e.g. no mic connected)
  python start.py --no-vision       # skip the camera
  python start.py --only face       # just face-engine (handy for UI work)
"""
import argparse
import os
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PY = sys.executable

# Force UTF-8 on the parent stdout so child output with non-cp1252 chars
# (smart quotes, unicode dashes, etc.) doesn't kill the pipe thread.
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


def _win_make_job():
    """Create a Windows Job Object set to kill all assigned processes when the
    launcher dies. Without this, killing start.py leaves children orphaned.
    Returns (job_handle, assign_func) or (None, None) on non-Windows/failure."""
    if os.name != "nt":
        return None, None
    try:
        import ctypes
        from ctypes import wintypes
        k32 = ctypes.windll.kernel32
        JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x00002000
        ExtendedInfoClass = 9
        job = k32.CreateJobObjectW(None, None)
        if not job:
            return None, None

        class IO_COUNTERS(ctypes.Structure):
            _fields_ = [("ReadOperationCount", ctypes.c_ulonglong),
                        ("WriteOperationCount", ctypes.c_ulonglong),
                        ("OtherOperationCount", ctypes.c_ulonglong),
                        ("ReadTransferCount", ctypes.c_ulonglong),
                        ("WriteTransferCount", ctypes.c_ulonglong),
                        ("OtherTransferCount", ctypes.c_ulonglong)]

        class JOBOBJECT_BASIC_LIMIT_INFORMATION(ctypes.Structure):
            _fields_ = [("PerProcessUserTimeLimit", ctypes.c_int64),
                        ("PerJobUserTimeLimit", ctypes.c_int64),
                        ("LimitFlags", wintypes.DWORD),
                        ("MinimumWorkingSetSize", ctypes.c_size_t),
                        ("MaximumWorkingSetSize", ctypes.c_size_t),
                        ("ActiveProcessLimit", wintypes.DWORD),
                        ("Affinity", ctypes.c_size_t),
                        ("PriorityClass", wintypes.DWORD),
                        ("SchedulingClass", wintypes.DWORD)]

        class JOBOBJECT_EXTENDED_LIMIT_INFORMATION(ctypes.Structure):
            _fields_ = [("BasicLimitInformation", JOBOBJECT_BASIC_LIMIT_INFORMATION),
                        ("IoInfo", IO_COUNTERS),
                        ("ProcessMemoryLimit", ctypes.c_size_t),
                        ("JobMemoryLimit", ctypes.c_size_t),
                        ("PeakProcessMemoryUsed", ctypes.c_size_t),
                        ("PeakJobMemoryUsed", ctypes.c_size_t)]

        info = JOBOBJECT_EXTENDED_LIMIT_INFORMATION()
        info.BasicLimitInformation.LimitFlags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        ok = k32.SetInformationJobObject(job, ExtendedInfoClass,
                                         ctypes.byref(info), ctypes.sizeof(info))
        if not ok:
            return None, None

        def assign(pid):
            PROCESS_ALL_ACCESS = 0x1F0FFF
            h = k32.OpenProcess(PROCESS_ALL_ACCESS, False, pid)
            if not h:
                return False
            try:
                return bool(k32.AssignProcessToJobObject(job, h))
            finally:
                k32.CloseHandle(h)

        return job, assign
    except Exception as e:
        print(f"[start] job-object unavailable: {e}", flush=True)
        return None, None

HTTP_PORT = 7897
WEB_URL = f"http://127.0.0.1:{HTTP_PORT}/face/web-face.html"

COMPONENTS = [
    # (tag, argv, flag-name) — argv is a list so http.server can be inline.
    ("vision",   [PY, str(ROOT / "ears" / "vision.py")],           "vision"),
    ("listener", [PY, str(ROOT / "ears" / "listener.py")],         "listener"),
    ("face",     [PY, str(ROOT / "face" / "face-engine.py")],      "face"),
    ("wake",     [PY, str(ROOT / "ears" / "wake_watcher.py")],     "wake"),
    ("sheet",    [PY, str(ROOT / "ears" / "sheet_maintainer.py")], "sheet"),
    ("http",     [PY, "-m", "http.server", str(HTTP_PORT), "--bind", "127.0.0.1"], "http"),
]

COLORS = {
    "vision":   "\033[36m",   # cyan
    "listener": "\033[33m",   # yellow
    "face":     "\033[35m",   # magenta
    "wake":     "\033[32m",   # green
    "sheet":    "\033[34m",   # blue
    "http":     "\033[90m",   # grey
    "reset":    "\033[0m",
}


def _pipe(proc, tag):
    color = COLORS.get(tag, "")
    reset = COLORS["reset"]
    for line in iter(proc.stdout.readline, b""):
        try:
            text = line.decode("utf-8", errors="replace").rstrip()
        except Exception:
            text = repr(line)
        try:
            print(f"{color}[{tag:<8}]{reset} {text}", flush=True)
        except UnicodeEncodeError:
            # Belt-and-suspenders: if the parent terminal still can't render
            # a code point, fall through with ascii-safe replacement.
            safe = text.encode("ascii", errors="replace").decode("ascii")
            print(f"{color}[{tag:<8}]{reset} {safe}", flush=True)
    proc.stdout.close()


def main():
    ap = argparse.ArgumentParser()
    for tag, _, _ in COMPONENTS:
        ap.add_argument(f"--no-{tag}", action="store_true")
    ap.add_argument("--only", choices=[c[0] for c in COMPONENTS])
    ap.add_argument("--open", action="store_true", help="launch chrome to the face URL after startup")
    args = ap.parse_args()

    selected = []
    for tag, argv, _flag in COMPONENTS:
        if args.only:
            if args.only == tag:
                selected.append((tag, argv))
            continue
        if getattr(args, f"no_{tag}"):
            continue
        selected.append((tag, argv))

    if not selected:
        print("[start] nothing to run", file=sys.stderr)
        return 2

    job_handle, assign_to_job = _win_make_job()
    if job_handle:
        print("[start] children bound to job-object — will die with launcher", flush=True)

    procs = []
    try:
        for tag, argv in selected:
            print(f"[start] launching {tag}", flush=True)
            p = subprocess.Popen(
                argv,
                cwd=str(ROOT),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                bufsize=1,
            )
            procs.append((tag, p))
            if assign_to_job:
                assign_to_job(p.pid)
            threading.Thread(target=_pipe, args=(p, tag), daemon=True).start()
            time.sleep(0.4)  # let each one print its banner before the next starts

        print(f"[start] all up — PIDs: " + ", ".join(f"{t}={p.pid}" for t, p in procs), flush=True)
        if args.open:
            chrome_paths = [
                r"C:\Program Files\Google\Chrome\Application\chrome.exe",
                r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
            ]
            opened = False
            for cp in chrome_paths:
                if Path(cp).exists():
                    try:
                        subprocess.Popen([cp, "--new-window", WEB_URL])
                        print(f"[start] chrome -> {WEB_URL}", flush=True)
                        opened = True
                    except Exception as e:
                        print(f"[start] chrome launch failed: {e}", flush=True)
                    break
            if not opened:
                try:
                    import webbrowser
                    webbrowser.open(WEB_URL)
                    print(f"[start] default browser -> {WEB_URL}", flush=True)
                except Exception as e:
                    print(f"[start] open failed: {e}", flush=True)
        print("[start] Ctrl+C to stop all", flush=True)

        # Block until any child exits OR we get interrupted.
        while True:
            time.sleep(0.5)
            for tag, p in procs:
                if p.poll() is not None:
                    print(f"[start] {tag} exited with code {p.returncode}", flush=True)
                    raise KeyboardInterrupt
    except KeyboardInterrupt:
        print("\n[start] shutting down...", flush=True)
    finally:
        for tag, p in procs:
            if p.poll() is None:
                try:
                    if os.name == "nt":
                        p.terminate()
                    else:
                        p.send_signal(signal.SIGINT)
                except Exception:
                    pass
        deadline = time.time() + 4.0
        for tag, p in procs:
            while p.poll() is None and time.time() < deadline:
                time.sleep(0.1)
            if p.poll() is None:
                print(f"[start] force-killing {tag}", flush=True)
                try:
                    p.kill()
                except Exception:
                    pass
        print("[start] clean.", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
