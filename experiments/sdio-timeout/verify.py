#!/usr/bin/env python3
"""Compile the exact upstream poll function with host stubs, baseline vs patch."""
import argparse
import json
from pathlib import Path
import re
import subprocess
import tempfile

HERE = Path(__file__).resolve().parent
CASES = ["read-pending", "read-deadline", "read-before-wrap", "read-after-wrap",
         "read-wrapped-deadline", "write-before-wrap", "stop-before-wrap", "write-after-wrap",
         "write-expired-after-wrap", "stop-expired", "write-deadline", "read-success", "disabled"]


def function(text):
    start = text.index("static bool sdcardSdio_poll(void)")
    opening = text.index("{", start)
    depth = 0
    for pos in range(opening, len(text)):
        if text[pos] == "{":
            depth += 1
        elif text[pos] == "}":
            depth -= 1
            if not depth:
                return text[start:pos + 1]
    raise ValueError("Unterminated upstream function")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("checkout", type=Path)
    args = parser.parse_args()
    lock = json.loads((HERE / "upstream.json").read_text())
    checkout = args.checkout.resolve()
    def upstream(path):
        return subprocess.check_output(["git", "-C", str(checkout), "show", f"{lock['commit']}:{path}"], text=True)
    baseline = upstream(lock["source"])
    impl = upstream("src/main/drivers/sdcard_impl.h")
    standard = upstream("src/main/drivers/sdcard_standard.h")
    states = re.search(r"typedef enum \{[^}]+\} sdcardState_e;", impl).group()
    status = re.search(r"typedef enum \{[^}]+\} sdcardReceiveBlockStatus_e;", baseline).group()
    defines = "\n".join(re.findall(r"^#define SDCARD_(?:BLOCK_SIZE|TIMEOUT_\w+)\s+\d+.*$", standard + "\n" + impl, re.M))
    results = {"upstream_commit": lock["commit"], "scope": "actual poll function with host stubs", "variants": {}}
    with tempfile.TemporaryDirectory(prefix="sdio-rollover-") as temp:
        root = Path(temp)
        source = root / lock["source"]
        source.parent.mkdir(parents=True)
        source.write_text(baseline)
        # Apply the distributed patch to the pinned source, never the user's checkout.
        subprocess.run(["git", "apply", "--check", str(HERE / "timeout-rollover.patch")], cwd=root, check=True)
        subprocess.run(["git", "apply", str(HERE / "timeout-rollover.patch")], cwd=root, check=True)
        for name, text in [("baseline", baseline), ("patched", source.read_text())]:
            program = root / f"{name}.c"
            program.write_text(states + "\n" + status + "\n" + defines + "\n" +
                               (HERE / "harness.h").read_text() + "\n" + function(text) + "\n" +
                               (HERE / "cases.c").read_text())
            executable = root / name
            subprocess.run(["cc", "-std=c11", "-Wall", "-Wextra", "-Werror", "-Wno-implicit-fallthrough",
                            str(program), "-o", str(executable)], check=True)
            codes = {label: subprocess.run([str(executable), str(i)], timeout=3).returncode
                     for i, label in enumerate(CASES)}
            results["variants"][name] = codes
    expected_failures = {"read-before-wrap", "write-before-wrap", "stop-before-wrap"}
    actual_failures = {k for k, v in results["variants"]["baseline"].items() if v}
    passed = actual_failures == expected_failures and not any(results["variants"]["patched"].values())
    results["passed"] = passed
    print(json.dumps(results, indent=2))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
