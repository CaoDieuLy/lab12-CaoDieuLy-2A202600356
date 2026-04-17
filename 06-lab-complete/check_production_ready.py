"""
Production readiness checker for Day 12 final project.

Run:
    python check_production_ready.py
"""
from __future__ import annotations

import os
import sys


def check(name: str, passed: bool, detail: str = "") -> dict[str, object]:
    icon = "[OK]" if passed else "[NO]"
    suffix = f" - {detail}" if detail else ""
    print(f"  {icon} {name}{suffix}")
    return {"name": name, "passed": passed}


def _read(path: str) -> str:
    with open(path, "r", encoding="utf-8") as file:
        return file.read()


def run_checks() -> bool:
    results: list[dict[str, object]] = []
    base = os.path.dirname(__file__)

    print("\n" + "=" * 56)
    print("  Production Readiness Check - Day 12")
    print("=" * 56)

    print("\nRequired Files")
    required = [
        "Dockerfile",
        "docker-compose.yml",
        ".dockerignore",
        ".env.example",
        "requirements.txt",
        "app/main.py",
        "app/config.py",
        "app/auth.py",
        "app/rate_limiter.py",
        "app/cost_guard.py",
        "utils/mock_llm.py",
    ]
    for rel in required:
        results.append(check(f"{rel} exists", os.path.exists(os.path.join(base, rel))))

    has_deploy_config = any(
        os.path.exists(os.path.join(base, candidate)) for candidate in ["railway.toml", "render.yaml"]
    )
    results.append(check("railway.toml or render.yaml exists", has_deploy_config))

    print("\nSecurity")
    root_gitignore = os.path.join(base, "..", ".gitignore")
    local_gitignore = os.path.join(base, ".gitignore")
    env_ignored = False
    for path in [local_gitignore, root_gitignore]:
        if os.path.exists(path) and ".env" in _read(path):
            env_ignored = True
            break
    results.append(check(".env is ignored by git", env_ignored))

    main_path = os.path.join(base, "app", "main.py")
    if os.path.exists(main_path):
        main_py = _read(main_path).lower()
        results.append(check("/health endpoint defined", '"/health"' in main_py or "'/health'" in main_py))
        results.append(check("/ready endpoint defined", '"/ready"' in main_py or "'/ready'" in main_py))
        results.append(check("authentication wiring exists", "verify_api_key" in main_py))
        results.append(check("rate limiting wiring exists", "check_rate_limit" in main_py or "429" in main_py))
        results.append(check("graceful shutdown (sigterm)", "sigterm" in main_py))
        results.append(check("structured logging usage", "json.dumps" in main_py or '"event"' in main_py))
    else:
        results.append(check("app/main.py available for checks", False))

    print("\nDocker")
    dockerfile = os.path.join(base, "Dockerfile")
    if os.path.exists(dockerfile):
        content = _read(dockerfile).lower()
        results.append(check("multi-stage docker build", "as builder" in content or "as runtime" in content))
        results.append(check("non-root user", "user " in content or "useradd" in content))
        results.append(check("healthcheck instruction", "healthcheck" in content))
        results.append(check("slim/alpine base image", "slim" in content or "alpine" in content))
    else:
        results.append(check("Dockerfile available for checks", False))

    dockerignore = os.path.join(base, ".dockerignore")
    if os.path.exists(dockerignore):
        content = _read(dockerignore)
        results.append(check(".dockerignore includes .env", ".env" in content))
        results.append(check(".dockerignore includes __pycache__", "__pycache__" in content))
    else:
        results.append(check(".dockerignore available for checks", False))

    passed = sum(1 for item in results if item["passed"])
    total = len(results)
    percent = round((passed / total) * 100) if total else 0

    print("\n" + "=" * 56)
    print(f"  Result: {passed}/{total} checks passed ({percent}%)")
    if percent == 100:
        print("  Status: PRODUCTION READY")
    elif percent >= 80:
        print("  Status: Almost ready - fix remaining items.")
    else:
        print("  Status: Not ready - complete missing items.")
    print("=" * 56 + "\n")

    return percent == 100


if __name__ == "__main__":
    is_ready = run_checks()
    sys.exit(0 if is_ready else 1)
