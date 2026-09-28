"""Exercise rosdev's lifecycle with an isolated Apple container CLI substitute.

Run with: python3 -m unittest discover -s tests -v
No real container runtime, network requests, or browser is used.
"""

import json
import os
from pathlib import Path
import shutil
import subprocess
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


if __name__ == "__main__":
    unittest.main()
