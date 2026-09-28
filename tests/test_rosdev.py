"""Exercise rosdev's lifecycle with an isolated Apple container CLI substitute.

Run with: python3 -m unittest discover -s tests -v
No real container runtime, network requests, or browser is used.
"""

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


REPO = Path(__file__).resolve().parents[1]
BASE = "ghcr.io/davidseysergit/ros2-dev:latest"

# Responses follow Apple container 1.4's published inspect schema. Unknown
# operations fail, so a newly introduced runtime dependency cannot silently pass.
FAKE_CLI = r'''#!/usr/bin/env python3
import json, os, pathlib, sys

root = pathlib.Path(os.environ["ROSDEV_TEST_RUNTIME"])
state_file = root / "state.json"
state = json.loads(state_file.read_text())
args = sys.argv[1:]
tool = pathlib.Path(sys.argv[0]).name
with (root / "calls.jsonl").open("a") as f:
    f.write(json.dumps([tool] + args) + "\n")

def save():
    state_file.write_text(json.dumps(state))

def missing(message):
    print(message, file=sys.stderr)
    sys.exit(1)

if tool in ("curl", "open"):
    sys.exit(0)
if args[:2] == ["system", "status"]:
    sys.exit(0)
if args[:2] == ["system", "start"]:
    sys.exit(0)
if args[:2] == ["image", "inspect"]:
    name = args[2]
    if name not in state["images"]:
        missing("image not found: " + name)
    print(json.dumps([{"configuration": {
        "name": name, "descriptor": {"digest": state["images"][name]}
    }}]))
elif args[:2] == ["image", "pull"]:
    state["images"][args[-1]] = "sha256:pulled"
    save()
elif args[:1] == ["build"]:
    if state.get("fail_build"):
        missing("deliberate build failure")
    state["build_count"] = state.get("build_count", 0) + 1
    name = args[args.index("-t") + 1]
    state["images"][name] = "sha256:build-" + str(state["build_count"])
    save()
elif args[:2] == ["network", "inspect"]:
    name = args[-1]
    if name not in state.get("networks", []):
        missing("network not found")
    print(json.dumps([{"id": name, "configuration": {"id": name}}]))
elif args[:2] == ["network", "create"]:
    state.setdefault("networks", []).append(args[-1])
    save()
elif args[:1] == ["inspect"]:
    name = args[1]
    if name not in state["containers"]:
        missing("container not found: " + name)
    print(json.dumps([state["containers"][name]]))
elif args[:1] == ["run"]:
    if state.get("fail_run"):
        missing("deliberate container start failure")
    options = {}
    positional = []
    i = 1
    while i < len(args):
        arg = args[i]
        if arg in ("--detach", "--rm", "--init"):
            i += 1
        elif arg.startswith("-"):
            options.setdefault(arg, []).append(args[i + 1])
            i += 2
        else:
            positional = args[i:]
            break
    name = options["--name"][0]
    if name in state["containers"]:
        missing("container already exists: " + name)
    image = positional[0]
    labels = dict(value.split("=", 1) for value in options.get("--label", []))
    state["containers"][name] = {
        "configuration": {
            "id": name, "labels": labels,
            "image": {"reference": image,
                      "descriptor": {"digest": state["images"][image]}},
        },
        "status": {"state": "running", "networks": [
            {"ipv4Address": "192.168.65.2/24", "network": "rosdev"}
        ]},
        "test_run_options": options,
    }
    save()
elif args[:1] in (["stop"], ["start"]):
    name = args[-1]
    if name not in state["containers"]:
        missing("container not found: " + name)
    state["containers"][name]["status"]["state"] = (
        "running" if args[0] == "start" else "stopped"
    )
    save()
elif args[:1] == ["delete"]:
    state["containers"].pop(args[-1], None)
    save()
elif args[:1] == ["exec"]:
    if "supervisorctl" in args and "status" in args:
        print("code RUNNING")
    if any(a.endswith("screenshot.py") for a in args):
        sys.stdout.buffer.write(state.get("screenshot", "\x89PNG\r\n\x1a\nfake").encode("latin-1"))
elif args[:2] == ["builder", "stop"]:
    pass
elif args[:1] in (["list"], ["logs"]):
    print(json.dumps(list(state["containers"].values())))
else:
    print("unsupported fake command: " + repr(args), file=sys.stderr)
    sys.exit(2)
'''


class RosdevLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="rosdev tests ")
        self.addCleanup(self.temp.cleanup)
        self.base_dir = Path(self.temp.name).resolve()
        self.root = self.base_dir / "setup with spaces"
        self.root.mkdir()
        shutil.copy2(REPO / "rosdev", self.root / "rosdev")
        for directory in ("local.example", "addons"):
            shutil.copytree(REPO / directory, self.root / directory)
        (self.root / "tools").mkdir()
        self.runtime = self.base_dir / "fake runtime"
        self.runtime.mkdir()
        self.bin = self.runtime / "bin"
        self.bin.mkdir()
        for name in ("container", "curl", "open"):
            executable = self.bin / name
            executable.write_text(FAKE_CLI)
            executable.chmod(0o755)
        self.save_state({"images": {BASE: "sha256:base-v1"}, "containers": {}})
        self.env = {
            key: value for key, value in os.environ.items()
            if not key.startswith("ROS2_") and key not in ("ROS_DOMAIN_ID", "RESOLUTION")
        }
        self.env.update({
            "PATH": str(self.bin) + os.pathsep + os.environ["PATH"],
            "ROSDEV_TEST_RUNTIME": str(self.runtime),
            "ROS2_OPEN_BROWSER": "0",
        })

    def state(self):
        return json.loads((self.runtime / "state.json").read_text())

    def save_state(self, state):
        (self.runtime / "state.json").write_text(json.dumps(state))

    def calls(self):
        journal = self.runtime / "calls.jsonl"
        return [json.loads(line) for line in journal.read_text().splitlines()] if journal.exists() else []

    def reset_calls(self):
        (self.runtime / "calls.jsonl").write_text("")

    def runtime_calls(self, command):
        return [call[1:] for call in self.calls() if call[:2] == ["container", command]]

    def rosdev(self, *args, ok=True, cwd=None, setup=None):
        setup = setup or self.root
        result = subprocess.run(
            ["bash", str(setup / "rosdev"), *args],
            cwd=cwd or setup, env=self.env, text=True,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=15,
        )
        if ok:
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        else:
            self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        return result

    def overlay(self):
        shutil.copytree(self.root / "local.example", self.root / "local", dirs_exist_ok=True)

    def run_options(self):
        return self.state()["containers"]["ros2"]["test_run_options"]

    def test_repeated_up_reuses_running_container_without_building(self):
        self.rosdev("up")
        self.reset_calls()
        self.rosdev("up")
        for command in ("build", "run", "start", "stop", "delete"):
            self.assertEqual(self.runtime_calls(command), [], command)

    def test_stopped_container_starts_without_recreation(self):
        self.rosdev("up")
        self.rosdev("down")
        self.reset_calls()
        self.rosdev("up")
        self.assertEqual(self.runtime_calls("start"), [["start", "ros2"]])
        self.assertEqual(self.runtime_calls("run"), [])
        self.assertEqual(self.runtime_calls("build"), [])

    def test_changed_overlay_file_rebuilds_and_recreates_once(self):
        self.overlay()
        source = self.root / "local" / "custom settings.txt"
        source.write_text("first version\n")
        self.rosdev("up")
        self.reset_calls()
        self.rosdev("up")
        self.assertEqual(self.runtime_calls("build"), [])
        source.write_text("second version\n")
        self.reset_calls()
        self.rosdev("up")
        self.assertEqual(len(self.runtime_calls("build")), 1)
        self.assertEqual(len(self.runtime_calls("stop")), 1)
        self.assertEqual(len(self.runtime_calls("delete")), 1)
        self.assertEqual(len(self.runtime_calls("run")), 1)
        self.reset_calls()
        self.rosdev("up")
        self.assertEqual(self.runtime_calls("build"), [])
        self.assertEqual(self.runtime_calls("run"), [])

    def test_failed_overlay_build_preserves_container_and_is_retried(self):
        self.overlay()
        self.rosdev("up")
        existing = self.state()["containers"]["ros2"]
        with (self.root / "local" / "Dockerfile").open("a") as f:
            f.write("\nENV CUSTOM_SETTING=changed\n")
        state = self.state()
        state["fail_build"] = True
        self.save_state(state)
        self.reset_calls()
        self.rosdev("up", ok=False)
        self.assertEqual(self.state()["containers"]["ros2"], existing)
        self.assertEqual(self.runtime_calls("stop"), [])
        state = self.state()
        state["fail_build"] = False
        self.save_state(state)
        self.reset_calls()
        self.rosdev("up")
        self.assertEqual(len(self.runtime_calls("build")), 1)
        self.assertEqual(len(self.runtime_calls("run")), 1)

    def test_image_digest_change_recreates_container(self):
        self.rosdev("up")
        state = self.state()
        state["images"][BASE] = "sha256:base-v2"
        self.save_state(state)
        self.reset_calls()
        self.rosdev("up")
        self.assertEqual(len(self.runtime_calls("run")), 1)
        self.assertEqual(self.runtime_calls("build"), [])
        self.assertEqual(self.state()["containers"]["ros2"]["configuration"]["image"]["descriptor"]["digest"], "sha256:base-v2")

    def test_base_digest_change_rebuilds_overlay_without_forced_pull(self):
        self.overlay()
        self.rosdev("up")
        state = self.state()
        state["images"][BASE] = "sha256:base-v2"
        self.save_state(state)
        self.reset_calls()
        self.rosdev("up")
        builds = self.runtime_calls("build")
        self.assertEqual(len(builds), 1)
        self.assertIn("BASE=" + BASE, builds[0])
        self.assertNotIn("--pull", builds[0])
        self.assertEqual(len(self.runtime_calls("run")), 1)

    def test_failed_base_rebuild_does_not_select_nonexistent_image(self):
        self.rosdev("up")
        state = self.state()
        state["fail_build"] = True
        self.save_state(state)
        self.rosdev("rebuild", ok=False)
        self.reset_calls()
        self.rosdev("up")
        self.assertEqual(self.runtime_calls("run"), [])
        self.assertEqual(self.runtime_calls("build"), [])
        self.assertFalse(any(arg.startswith("ros2-dev:local-") for call in self.calls() for arg in call))

    def test_two_checkouts_keep_their_custom_images_separate(self):
        self.overlay()
        self.rosdev("up")
        first_image = self.state()["containers"]["ros2"]["configuration"]["image"]
        second_root = self.base_dir / "another checkout"
        second_root.mkdir()
        shutil.copy2(self.root / "rosdev", second_root / "rosdev")
        (second_root / "tools").mkdir()
        shutil.copytree(self.root / "local.example", second_root / "local")
        (second_root / "local" / "extra.txt").write_text("different custom image\n")
        (second_root / ".env").write_text(
            "ROS2_CONTAINER=ros2-second\nROS2_DESKTOP_PORT=16080\nROS2_CODE_PORT=18080\n"
        )
        self.rosdev("up", setup=second_root)
        second_image = self.state()["containers"]["ros2-second"]["configuration"]["image"]
        self.assertNotEqual(first_image["reference"], second_image["reference"])
        self.reset_calls()
        self.rosdev("up")
        self.assertEqual(self.runtime_calls("build"), [])
        self.assertEqual(self.runtime_calls("run"), [])
        self.assertEqual(self.state()["images"][first_image["reference"]], first_image["descriptor"]["digest"])

    def test_successful_base_rebuild_persists_without_clobbering_other_checkouts(self):
        self.rosdev("rebuild")
        first_image = self.state()["containers"]["ros2"]["configuration"]["image"]
        self.assertTrue(first_image["reference"].startswith("ros2-dev:local-"))
        second_root = self.base_dir / "second base checkout"
        second_root.mkdir()
        shutil.copy2(self.root / "rosdev", second_root / "rosdev")
        (second_root / "tools").mkdir()
        (second_root / ".env").write_text(
            "ROS2_CONTAINER=ros2-second\nROS2_DESKTOP_PORT=16080\nROS2_CODE_PORT=18080\n"
        )
        self.rosdev("rebuild", setup=second_root)
        second_image = self.state()["containers"]["ros2-second"]["configuration"]["image"]
        self.assertNotEqual(first_image["reference"], second_image["reference"])
        self.reset_calls()
        self.rosdev("up")
        self.assertEqual(self.runtime_calls("build"), [])
        self.assertEqual(self.runtime_calls("run"), [])
        self.assertEqual(self.state()["images"][first_image["reference"]], first_image["descriptor"]["digest"])

    def test_failed_container_run_exits_without_opening_browser_and_can_retry(self):
        state = self.state()
        state["fail_run"] = True
        self.save_state(state)
        self.env["ROS2_OPEN_BROWSER"] = "1"
        result = self.rosdev("up", ok=False)
        self.assertIn("deliberate container start failure", result.stderr)
        self.assertEqual(self.state()["containers"], {})
        self.assertFalse(any(call[0] in ("open", "curl") for call in self.calls()))
        state = self.state()
        state["fail_run"] = False
        self.save_state(state)
        self.reset_calls()
        self.rosdev("up")
        self.assertEqual(len(self.runtime_calls("run")), 1)

    def test_explicit_release_tag_overrides_previously_built_local_base(self):
        self.rosdev("rebuild")
        self.env["ROS2_DEV_TAG"] = "v0.2.0"
        self.reset_calls()
        self.rosdev("up")
        image = self.state()["containers"]["ros2"]["configuration"]["image"]
        self.assertEqual(image["reference"], "ghcr.io/davidseysergit/ros2-dev:v0.2.0")
        self.assertEqual(self.runtime_calls("build"), [])

    def test_workspace_paths_with_spaces_get_separate_reusable_cache_volumes(self):
        self.overlay()
        self.rosdev("up")
        original = self.run_options()["--volume"]
        original_cache = {v for v in original if v.startswith("rosdev-")}
        self.assertEqual(len(original_cache), 4)
        caller = self.base_dir / "caller folder"
        caller.mkdir()
        target = self.base_dir / "second workspace"
        self.reset_calls()
        self.rosdev("ws", "use", "../second workspace", cwd=caller)
        switched = self.run_options()["--volume"]
        switched_cache = {v for v in switched if v.startswith("rosdev-")}
        self.assertIn(str(target) + ":/home/ros/ws", switched)
        self.assertTrue((target / "src").is_dir())
        self.assertEqual(len(switched_cache), 4)
        self.assertTrue(original_cache.isdisjoint(switched_cache))
        self.assertEqual(self.runtime_calls("build"), [])
        self.reset_calls()
        self.rosdev("ws", "use", str(self.root / "ws"))
        restored = {v for v in self.run_options()["--volume"] if v.startswith("rosdev-")}
        self.assertEqual(restored, original_cache)
        self.assertEqual(self.runtime_calls("build"), [])

    def test_all_service_ports_are_published_on_loopback(self):
        self.env.update({"ROS2_DESKTOP_PORT": "16080", "ROS2_CODE_PORT": "18080"})
        addon = self.root / "local" / "addons" / "foxglove"
        addon.mkdir(parents=True)
        (addon / "ports").write_text("8765\n")
        self.rosdev("up")
        self.assertEqual(set(self.run_options()["--publish"]), {
            "127.0.0.1:16080:6080", "127.0.0.1:18080:8080", "127.0.0.1:8765:8765",
        })

    def test_addon_path_traversal_is_rejected_before_mutation(self):
        for name in ("../foxglove", "../../outside", "foxglove;touch marker", ""):
            with self.subTest(name=name):
                self.rosdev("addon", "add", name, ok=False)
                self.assertFalse((self.root / "local").exists())
                self.assertEqual(self.runtime_calls("build"), [])
                self.assertEqual(self.runtime_calls("run"), [])

    def test_addon_invalid_port_is_rejected_before_container_changes(self):
        self.rosdev("up")
        addon = self.root / "local" / "addons" / "foxglove"
        addon.mkdir(parents=True)
        for port in ("0", "65536", "0.0.0.0:8765", "8765;touch marker"):
            with self.subTest(port=port):
                (addon / "ports").write_text(port + "\n")
                self.reset_calls()
                self.rosdev("up", ok=False)
                for command in ("stop", "delete", "run"):
                    self.assertEqual(self.runtime_calls(command), [], command)

    def test_invalid_service_port_preserves_running_container(self):
        self.rosdev("up")
        for variable, port in (("ROS2_CODE_PORT", "garbage"), ("ROS2_DESKTOP_PORT", "65536")):
            with self.subTest(variable=variable):
                self.env[variable] = port
                self.reset_calls()
                self.rosdev("up", ok=False)
                for command in ("stop", "delete", "run"):
                    self.assertEqual(self.runtime_calls(command), [], command)
                del self.env[variable]

    def test_unrelated_container_is_never_stopped_or_deleted(self):
        self.rosdev("up")
        state = self.state()
        state["containers"]["ros2"]["configuration"]["labels"]["rosdev.root"] = "/another/setup"
        self.save_state(state)
        for command in ("up", "down", "restart", "uninstall"):
            with self.subTest(command=command):
                self.reset_calls()
                self.rosdev(command, ok=False)
                self.assertEqual(self.runtime_calls("stop"), [])
                self.assertEqual(self.runtime_calls("delete"), [])
                self.assertIn("ros2", self.state()["containers"])

    def test_new_package_arguments_are_passed_without_shell_interpretation(self):
        self.rosdev("new", "example; touch /tmp/unwanted", "cpp")
        command = self.runtime_calls("exec")[-1]
        self.assertEqual(command[-2:], ["example; touch /tmp/unwanted", "cpp"])
        self.assertNotIn("example; touch /tmp/unwanted", command[4])

    def test_launch_arguments_are_passed_without_shell_interpretation(self):
        self.rosdev("launch", "demo", "my_pkg", "demo.launch.py", "use_sim:=true; touch /tmp/unwanted")
        command = self.runtime_calls("exec")[-1]
        self.assertIn("jobs.sh start", command[4])
        self.assertEqual(command[-4:], ["demo", "my_pkg", "demo.launch.py", "use_sim:=true; touch /tmp/unwanted"])
        self.assertNotIn("unwanted", command[4])

    def test_job_commands_need_their_arguments(self):
        for args in (["launch", "demo", "my_pkg"], ["start", "demo"], ["stop"]):
            with self.subTest(args=args):
                self.reset_calls()
                self.rosdev(*args, ok=False)
                self.assertEqual(self.runtime_calls("exec"), [])

    def test_logs_with_a_name_shows_a_job_and_without_shows_the_container(self):
        self.rosdev("logs", "demo", "-n", "5")
        command = self.runtime_calls("exec")[-1]
        self.assertIn("jobs.sh log", command[4])
        self.assertEqual(command[-3:], ["demo", "-n", "5"])
        self.reset_calls()
        self.rosdev("logs")
        self.assertEqual(self.runtime_calls("logs"), [["logs", "--follow", "ros2"]])

    def test_test_arguments_reach_the_runner_unchanged(self):
        self.rosdev("test", "my_pkg", "--filter", "Suite.*:-Suite.Slow", "--json")
        command = self.runtime_calls("exec")[-1]
        self.assertIn("test.sh", command[4])
        self.assertEqual(command[-4:], ["my_pkg", "--filter", "Suite.*:-Suite.Slow", "--json"])

    def test_screenshot_is_saved_relative_to_the_caller(self):
        elsewhere = self.base_dir / "caller dir"
        elsewhere.mkdir()
        result = self.rosdev("screenshot", "shot.png", "--scale", "0.5", cwd=elsewhere)
        self.assertEqual(result.stdout.strip(), str(elsewhere / "shot.png"))
        self.assertTrue((elsewhere / "shot.png").read_bytes().startswith(b"\x89PNG"))
        self.assertEqual(self.runtime_calls("exec")[-1][-2:], ["--scale", "0.5"])

    def test_screenshot_that_is_not_a_png_leaves_no_file(self):
        state = self.state()
        state["screenshot"] = "Welcome to the shell\n"
        self.save_state(state)
        self.rosdev("screenshot", "shot.png", ok=False)
        self.assertEqual(list(self.root.glob("shot.png*")), [])
        self.rosdev("screenshot", "--bogus", ok=False)

    def test_unedited_old_workspace_instructions_are_pointed_out_but_not_changed(self):
        template = self.root / "workspace.example" / "CLAUDE.md"
        template.parent.mkdir()
        git = ["git", "-C", str(self.root), "-c", "user.name=t", "-c", "user.email=t@example.com"]
        subprocess.run(git + ["init", "-q"], check=True)
        for version in ("old instructions\n", "new instructions\n"):
            template.write_text(version)
            subprocess.run(git + ["add", "workspace.example"], check=True)
            subprocess.run(git + ["commit", "-qm", version], check=True)
        workspace = self.base_dir / "ws"
        (workspace / "src").mkdir(parents=True)
        self.env["ROS2_WS"] = str(workspace)
        self.rosdev("up")
        for content, noted in (("old instructions\n", True), ("my own notes\n", False),
                                ("new instructions\n", False)):
            with self.subTest(content=content):
                (workspace / "CLAUDE.md").write_text(content)
                result = self.rosdev("doctor")
                self.assertEqual("older copy of the agent instructions" in result.stdout, noted, result.stdout)
                self.assertEqual((workspace / "CLAUDE.md").read_text(), content)

    def test_update_notice_compares_the_cached_published_digest(self):
        state_dir = self.root / "local" / ".rosdev"
        state_dir.mkdir(parents=True, exist_ok=True)
        for cached, env, noticed in (("sha256:base-v1", {}, False), ("sha256:newer", {}, True),
                                     ("sha256:newer", {"ROS2_UPDATE_CHECK": "0"}, False),
                                     ("not a digest", {}, False)):
            with self.subTest(cached=cached, env=env):
                (state_dir / "update-check").write_text(cached + "\n")
                self.env.update(env)
                result = self.rosdev("status")
                self.assertEqual("Update available" in result.stderr, noticed, result.stderr)
                for key in env:
                    del self.env[key]
        # Commands whose output agents parse never get the notice.
        self.assertNotIn("Update available", self.rosdev("exec", "true").stderr)

    def test_update_notice_skips_locally_built_images(self):
        self.env["ROS2_DEV_IMAGE"] = "my-own-image:dev"
        state = self.state()
        state["images"]["my-own-image:dev"] = "sha256:mine"
        self.save_state(state)
        state_dir = self.root / "local" / ".rosdev"
        state_dir.mkdir(parents=True, exist_ok=True)
        (state_dir / "update-check").write_text("sha256:newer\n")
        self.assertNotIn("Update available", self.rosdev("status").stderr)


class TestSummaryTests(unittest.TestCase):
    """tools/test_summary.py runs on the host too: it only reads JUnit XML."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.ws = Path(self.temp.name)
        self.results = self.ws / "build" / "pkg" / "test_results" / "pkg"
        self.results.mkdir(parents=True)
        self.log = self.ws / "run.log"
        self.log.write_text("colcon output\n")

    def write(self, name, body, age=0):
        path = self.results / name
        path.write_text(body)
        if age:
            os.utime(path, (path.stat().st_mtime - age,) * 2)

    def summarize(self, status=0):
        marker = self.ws / "marker"
        marker.touch()
        os.utime(marker, (marker.stat().st_mtime - 60,) * 2)
        result = subprocess.run(
            [sys.executable, str(REPO / "tools" / "test_summary.py"), "--since", str(marker), "--log", str(self.log),
             "--status", str(status), "--timeout", "900", "--domain", "150", "--json", "pkg"],
            cwd=self.ws, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=15)
        return result.returncode, json.loads(result.stdout)

    def test_failures_are_reported_with_their_message(self):
        self.write("a.gtest.xml", '<testsuites><testsuite><testcase classname="S" name="ok"/>'
                   '<testcase classname="S" name="bad"><failure message="expected 1, got 2"/></testcase>'
                   '<testcase classname="S" name="skip"><skipped/></testcase></testsuite></testsuites>')
        code, summary = self.summarize()
        self.assertEqual(code, 1)
        self.assertEqual((summary["tests"], summary["passed"], summary["failed"], summary["skipped"]), (3, 1, 1, 1))
        self.assertEqual(summary["failures"][0]["test"], "S.bad")
        self.assertIn("expected 1, got 2", summary["failures"][0]["message"])

    def test_results_from_earlier_runs_are_ignored(self):
        self.write("old.xml", '<testsuite><testcase name="t"><failure message="old"/></testcase></testsuite>', age=3600)
        self.write("new.xml", '<testsuite><testcase name="t"/></testsuite>')
        code, summary = self.summarize()
        self.assertEqual(code, 0)
        self.assertTrue(summary["ok"])
        self.assertEqual(summary["tests"], 1)

    def test_no_results_or_timeout_is_not_success(self):
        code, summary = self.summarize()
        self.assertEqual(code, 1)
        self.assertFalse(summary["ok"])
        self.assertIn("colcon output", summary["log_tail"])
        self.write("new.xml", '<testsuite><testcase name="t"/></testsuite>')
        code, summary = self.summarize(status=124)
        self.assertEqual(code, 124)
        self.assertTrue(summary["timed_out"])


if __name__ == "__main__":
    unittest.main()
