#!/usr/bin/env python3
"""Verify the full SDIO driver against the pinned upstream recovery PR."""
import argparse
import json
from pathlib import Path
import subprocess
import tempfile
import xml.etree.ElementTree as ET

HERE = Path(__file__).resolve().parent
TEST_FILE = "src/test/unit/sdcard_sdio_unittest.cc"
DRIVER = "src/main/drivers/sdcard_sdio_baremetal.c"
EXPECTED_FAILURES = {
    "ReadRemainsPendingAcrossRollover", "DmaWriteRemainsPendingAcrossRollover",
    "WriteCommitRemainsPendingAcrossRollover", "MultiBlockStopRemainsPendingAcrossRollover",
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("checkout", type=Path)
    parser.add_argument("--output", type=Path, default=Path("reports/sdio-recovery"))
    args = parser.parse_args()
    output = args.output.resolve(); output.mkdir(parents=True, exist_ok=True)
    lock = json.loads((HERE / "upstream.json").read_text())
    patch = HERE / "rollover-followup.patch"
    results = {"upstream_commit": lock["commit"], "scope": "complete production SDIO driver with host boundary stubs",
               "compiler": subprocess.check_output(["gcc", "--version"], text=True).splitlines()[0], "variants": {}}
    with tempfile.TemporaryDirectory(prefix="sdio-full-driver-") as temp:
        root = Path(temp)
        source = root / "source"
        subprocess.run(["git", "init", "--quiet", str(source)], check=True)
        subprocess.run(["git", "fetch", "--quiet", "--depth=1", str(args.checkout.resolve()), lock["commit"]],
                       cwd=source, check=True, timeout=60)
        subprocess.run(["git", "checkout", "--quiet", "--detach", lock["commit"]], cwd=source, check=True, timeout=60)
        subprocess.run(["git", "apply", "--check", str(patch)], cwd=source, check=True)
        subprocess.run(["git", "apply", f"--include={TEST_FILE}", str(patch)], cwd=source, check=True)
        for variant in ("baseline", "patched"):
            if variant == "patched":
                subprocess.run(["git", "apply", f"--include={DRIVER}", str(patch)], cwd=source, check=True)
            xml = output / f"{variant}.xml"
            # Unique build directories prevent object/coverage reuse between variants.
            xml_run = root / f"{variant}.xml"
            command = ["make", "-C", "src/test", "test_sdcard_sdio_unittest", "CC=gcc", "CXX=g++",
                       f"OBJECT_DIR={root / ('obj-' + variant)}", f"EXEC_OPTS=--gtest_output=xml:{xml_run}"]
            run = subprocess.run(command, cwd=source, text=True, stdout=subprocess.PIPE,
                                 stderr=subprocess.STDOUT, timeout=180)
            (output / f"{variant}.log").write_text(run.stdout)
            if not xml_run.exists():
                raise RuntimeError(f"{variant}: test report was not produced; inspect build log")
            xml.write_bytes(xml_run.read_bytes())
            cases = list(ET.parse(xml_run).getroot().iter("testcase"))
            failures = sorted(case.attrib["name"] for case in cases if case.find("failure") is not None)
            results["variants"][variant] = {"tests": len(cases), "failed": failures, "exit_code": run.returncode}
    baseline, patched = results["variants"]["baseline"], results["variants"]["patched"]
    results["passed"] = (baseline["tests"] == patched["tests"] == 19 and
                         set(baseline["failed"]) == EXPECTED_FAILURES and baseline["exit_code"] != 0 and
                         not patched["failed"] and patched["exit_code"] == 0)
    (output / "result.json").write_text(json.dumps(results, indent=2) + "\n")
    print(json.dumps(results, indent=2))
    return 0 if results["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
