"""
Fail if the current branch changed files outside its owner's paths (vs main).
Branch prefixes: p1a/ p1b/ p2/ final/. 'main' skips the check.
usage: python scripts/check_ownership.py [--base main]
"""
import fnmatch
import subprocess
import sys

OWNED = {
    "p1a/": ["src/proofkit/extraction/*", "tests/unit/extraction/*", "tests/acceptance/test_extraction_*",
             "fixtures/notes/*", "fixtures/findings/*"],
    "p1b/": ["src/proofkit/reasoning/*", "tests/unit/reasoning/*", "tests/acceptance/test_reasoning_*",
             "eval/*", "config/frailty_rules.json", "fixtures/decisions/*"],
    "p2/": ["src/proofkit/wallet/*", "tests/unit/wallet/*", "tests/acceptance/test_wallet_*",
            "config/wallet_rules.json", "fixtures/earnings_docs/*", "fixtures/earnings/*", "fixtures/wallet/*"],
    "final/": ["src/proofkit/integration/*", "app/*", "tests/integration/*"],
}
FROZEN = ["src/proofkit/contracts/*", "src/proofkit/common/*", "contracts/*", "tests/contract/*",
          "tests/conftest.py", "docs/02_CONTRACTS.md"]
ANYONE = ["docs/roles/*", "*/HANDOFF.md", "README.md", "setup/TRACKER.md", ".kiro/specs/*"]


def git(*args: str) -> str:
    return subprocess.run(["git", *args], capture_output=True, text=True, check=True).stdout.strip()


def main() -> int:
    base = sys.argv[sys.argv.index("--base") + 1] if "--base" in sys.argv else "main"
    try:
        branch = git("branch", "--show-current")
    except Exception:
        print("not a git repo, skipping ownership check")
        return 0
    if branch in ("main", "master", ""):
        print(f"on {branch or 'detached HEAD'}: ownership check skipped")
        return 0
    prefix = next((p for p in OWNED if branch.startswith(p)), None)
    if prefix is None:
        print(f"branch '{branch}' has no owner prefix ({', '.join(OWNED)}). Rename it.")
        return 1
    changed = set(git("diff", "--name-only", f"{base}...HEAD").splitlines())
    changed |= set(git("diff", "--name-only").splitlines()) | set(git("diff", "--name-only", "--cached").splitlines())
    changed |= set(git("ls-files", "--others", "--exclude-standard").splitlines())
    bad_frozen = [f for f in changed if any(fnmatch.fnmatch(f, p) for p in FROZEN)]
    outside = [f for f in changed if f and f not in bad_frozen
               and not any(fnmatch.fnmatch(f, p) for p in OWNED[prefix] + ANYONE)]
    if bad_frozen:
        print("FROZEN files changed (needs the contract change protocol):\n  " + "\n  ".join(sorted(bad_frozen)))
    if outside:
        print(f"files outside {prefix} ownership:\n  " + "\n  ".join(sorted(outside)))
    if bad_frozen or outside:
        return 1
    print(f"ownership OK for {branch} ({len(changed)} files)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
