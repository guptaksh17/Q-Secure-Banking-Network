#!/usr/bin/env python3
"""Cross-platform developer helper (Windows / macOS / Linux). Standard library only.

Windows:                         macOS / Linux:
  py -3.12 dev.py setup            python3.12 dev.py setup
  py -3.12 dev.py test             python3.12 dev.py test
  py -3.12 dev.py run              python3.12 dev.py run
  py -3.12 dev.py experiment NAME  python3.12 dev.py experiment NAME
  py -3.12 dev.py test-ui          python3.12 dev.py test-ui

setup  creates backend/.venv, installs backend/requirements.txt into it,
       copies backend/.env.example -> backend/.env (if missing), runs npm install.
test   runs pytest with the venv's interpreter (extra args are passed through,
       e.g. `dev.py test -k bb84 -m "not slow"`).
run    starts FastAPI on :8000 and Vite on :5173 together; Ctrl+C stops both.
experiment NAME  runs backend/experiments/NAME.py (e.g. channel_sweeps); extra args pass through.
test-ui  runs the frontend Vitest suite (npm test) and a production build.

No activation step is needed: every command calls the venv's python directly.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import time
import venv
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BACKEND = ROOT / "backend"
FRONTEND = ROOT / "frontend"
VENV_DIR = BACKEND / ".venv"
# Pinned requirements resolve to binary wheels on Windows and macOS only for 3.12
# (numpy 2.5 needs >= 3.12; some pins lack 3.13 wheels on macOS).
SUPPORTED_PYTHON = ((3, 12), (3, 12))


def venv_python() -> Path:
    if os.name == "nt":
        return VENV_DIR / "Scripts" / "python.exe"
    return VENV_DIR / "bin" / "python"


def _version_ok(version: tuple[int, int]) -> bool:
    return SUPPORTED_PYTHON[0] <= version <= SUPPORTED_PYTHON[1]


def _fmt(version: tuple[int, int]) -> str:
    return f"{version[0]}.{version[1]}"


def _supported_text() -> str:
    lo, hi = SUPPORTED_PYTHON
    return _fmt(lo) if lo == hi else f"{_fmt(lo)}-{_fmt(hi)}"


def run(cmd: list, cwd: Path) -> None:
    printable = " ".join(str(part) for part in cmd)
    print(f"\n[{cwd.name}] $ {printable}", flush=True)
    subprocess.run([str(part) for part in cmd], cwd=cwd, check=True)


def find_npm() -> str:
    npm = shutil.which("npm")  # resolves npm.cmd on Windows
    if npm is None:
        sys.exit("npm not found on PATH. Install Node.js 20 or 22 LTS, then reopen the terminal.")
    return npm


def require_venv() -> Path:
    python = venv_python()
    if not python.exists():
        sys.exit("backend/.venv not found. Run `dev.py setup` first.")
    return python


def cmd_setup(args: argparse.Namespace) -> None:
    current = sys.version_info[:2]
    if not _version_ok(current):
        sys.exit(
            f"This is Python {_fmt(current)}; the project needs Python {_supported_text()}.\n"
            "Windows: py -3.12 dev.py setup    macOS/Linux: python3.12 dev.py setup"
        )

    python = venv_python()
    if python.exists():
        out = subprocess.run(
            [str(python), "-c", "import sys; print(*sys.version_info[:2])"],
            capture_output=True, text=True,
        )
        existing = tuple(int(x) for x in out.stdout.split()) if out.returncode == 0 else ()
        if len(existing) != 2 or not _version_ok(existing):
            sys.exit(
                "backend/.venv exists but uses an unsupported or broken Python. "
                "Delete the backend/.venv folder and run setup again."
            )
        print(f"Reusing backend/.venv (Python {_fmt(existing)})")
    else:
        print(f"Creating backend/.venv with Python {_fmt(current)} ...")
        venv.EnvBuilder(with_pip=True).create(VENV_DIR)

    run([python, "-m", "pip", "install", "--upgrade", "pip"], BACKEND)
    run([python, "-m", "pip", "install", "-r", "requirements.txt"], BACKEND)

    env_file, env_example = BACKEND / ".env", BACKEND / ".env.example"
    if not env_file.exists():
        shutil.copyfile(env_example, env_file)
        print("Created backend/.env from .env.example")

    if args.skip_frontend:
        print("Skipping npm install (--skip-frontend).")
    else:
        run([find_npm(), "install"], FRONTEND)

    print("\nSetup complete. Next: `dev.py test`, then `dev.py run`.")


def cmd_test(args: argparse.Namespace) -> None:
    python = require_venv()
    result = subprocess.run([str(python), "-m", "pytest", *args.pytest_args], cwd=BACKEND)
    sys.exit(result.returncode)


def cmd_experiment(args: argparse.Namespace) -> None:
    python = require_venv()
    script = BACKEND / "experiments" / f"{args.name}.py"
    if not script.exists():
        available = sorted(p.stem for p in script.parent.glob("*.py") if p.stem != "__init__")
        sys.exit(f"No experiment {args.name!r}. Available: {', '.join(available)}")
    result = subprocess.run(
        [str(python), "-m", f"experiments.{args.name}", *args.extra_args], cwd=BACKEND
    )
    sys.exit(result.returncode)


def cmd_test_ui(args: argparse.Namespace) -> None:
    npm = find_npm()
    for script in ("test", "build"):
        result = subprocess.run([npm, "run", script], cwd=FRONTEND)
        if result.returncode:
            sys.exit(result.returncode)


def cmd_run(args: argparse.Namespace) -> None:
    python = require_venv()
    npm = find_npm()
    procs = [
        subprocess.Popen(
            [str(python), "-m", "uvicorn", "app.main:app", "--reload", "--port", "8000"],
            cwd=BACKEND,
        ),
        subprocess.Popen([npm, "run", "dev"], cwd=FRONTEND),
    ]
    print("Backend  http://127.0.0.1:8000/docs\nFrontend http://localhost:5173\nCtrl+C to stop.")
    try:
        while all(proc.poll() is None for proc in procs):
            time.sleep(0.5)
    except KeyboardInterrupt:
        pass
    finally:
        for proc in procs:
            if proc.poll() is None:
                proc.terminate()
        for proc in procs:
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()


def main() -> None:
    parser = argparse.ArgumentParser(description="Q-Secure Banking Network dev helper")
    sub = parser.add_subparsers(dest="command", required=True)

    setup = sub.add_parser("setup", help="create venv and install all dependencies")
    setup.add_argument("--skip-frontend", action="store_true", help="skip npm install")
    setup.set_defaults(func=cmd_setup)

    test = sub.add_parser("test", help="run backend pytest suite in the venv (extra args go to pytest)")
    test.set_defaults(func=cmd_test)

    serve = sub.add_parser("run", help="start backend and frontend dev servers")
    serve.set_defaults(func=cmd_run)

    test_ui = sub.add_parser("test-ui", help="run frontend unit tests and a production build")
    test_ui.set_defaults(func=cmd_test_ui)

    experiment = sub.add_parser("experiment", help="run backend/experiments/<name>.py in the venv")
    experiment.add_argument("name", help="e.g. channel_sweeps")
    experiment.set_defaults(func=cmd_experiment)

    # Unknown args are forwarded to pytest / the experiment script; other commands reject them.
    args, extra = parser.parse_known_args()
    if args.command not in ("test", "experiment") and extra:
        parser.error(f"unrecognized arguments: {' '.join(extra)}")
    args.pytest_args = args.extra_args = extra
    args.func(args)


if __name__ == "__main__":
    main()
