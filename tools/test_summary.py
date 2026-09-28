"""Summarize the JUnit XML files written by one `rosdev test` run.

Only files newer than --since are read, so stale results from earlier runs or
other packages never appear. Exit code: 0 all passed, 1 failures or no results,
124 time limit reached.
"""

import argparse
import json
import os
from pathlib import Path
import sys
import xml.etree.ElementTree as ET

ap = argparse.ArgumentParser()
ap.add_argument("packages", nargs="*")
ap.add_argument("--since", required=True)
ap.add_argument("--log", required=True)
ap.add_argument("--status", type=int, required=True)
ap.add_argument("--timeout", type=int, required=True)
ap.add_argument("--domain", required=True)
ap.add_argument("--json", action="store_true")
a = ap.parse_args()

since = os.path.getmtime(a.since)
os.unlink(a.since)
build = Path("build")
roots = [build / p for p in a.packages] if a.packages else [build]
def is_result(f):  # ament/ctest results live under test_results/; pytest writes pytest.xml
    return ("test_results" in f.parts or f.name == "pytest.xml") and f.stat().st_mtime >= since

files = sorted({f for r in roots if r.is_dir() for f in r.rglob("*.xml") if is_result(f)})

def first_lines(text, n=6):
    lines = [l for l in (text or "").strip().splitlines() if l.strip()]
    return "\n".join(lines[:n] + (["..."] if len(lines) > n else []))

tests = passed = skipped = 0
failures = []
per_package = {}
for f in files:
    package = f.relative_to(build).parts[0]
    try:
        root = ET.parse(f).getroot()
    except ET.ParseError as e:
        failures.append({"package": package, "test": f.name, "message": f"unreadable result file: {e}"})
        continue
    counts = per_package.setdefault(package, {"tests": 0, "failed": 0, "skipped": 0})
    for case in root.iter("testcase"):
        tests += 1; counts["tests"] += 1
        bad = case.find("failure")
        if bad is None:
            bad = case.find("error")
        if bad is not None:
            counts["failed"] += 1
            name = ".".join(x for x in (case.get("classname"), case.get("name")) if x)
            failures.append({"package": package, "test": name,
                             "message": first_lines(bad.get("message") or bad.text)})
        elif case.find("skipped") is not None:
            skipped += 1; counts["skipped"] += 1
        else:
            passed += 1

timed_out = a.status in (124, 137)
ok = not timed_out and a.status == 0 and not failures and tests > 0
log_tail = first_lines("\n".join(Path(a.log).read_text(errors="replace").splitlines()[-40:]), 40)
summary = {"ok": ok, "tests": tests, "passed": passed, "failed": len(failures), "skipped": skipped,
           "timed_out": timed_out, "colcon_exit_code": a.status, "ros_domain_id": int(a.domain),
           "packages": per_package, "failures": failures, "log": a.log}

if a.json:
    if not ok and not failures:
        summary["log_tail"] = log_tail
    print(json.dumps(summary, indent=2))
else:
    for p, c in per_package.items():
        print(f"{p}: {c['tests'] - c['failed'] - c['skipped']} passed, {c['failed']} failed, {c['skipped']} skipped")
    for fl in failures:
        print(f"\nFAILED {fl['package']}: {fl['test']}")
        if fl["message"]:
            print("  " + fl["message"].replace("\n", "\n  "))
    if timed_out:
        print(f"\nTime limit of {a.timeout}s reached; results above are partial.")
    elif tests == 0:
        print("\nNo test results were produced. Last output:\n" + log_tail)
    elif a.status and not failures:
        print(f"\ncolcon test exited with {a.status}. Last output:\n" + log_tail)
    print(f"\n{'PASSED' if ok else 'FAILED'}: {passed}/{tests} passed, {len(failures)} failed, "
          f"{skipped} skipped (ROS_DOMAIN_ID={a.domain}, full log: {a.log})")
sys.exit(124 if timed_out else 0 if ok else 1)
