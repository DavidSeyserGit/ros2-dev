# ROS 2 Jazzy + MoveIt 2 — browser desktop

Runs a full ROS 2 desktop in a container and shows it in your browser at
**http://localhost:6080**. Native arm64 on Apple Silicon: no emulation, no Docker Desktop.

- ROS 2 **Jazzy** (Ubuntu 24.04, LTS until 2029) + MoveIt 2.12
- Planning pipelines: **OMPL, CHOMP, Pilz industrial (PTP/LIN/CIRC), STOMP**
- XFCE desktop via TigerVNC + noVNC; RViz renders in software (Mesa llvmpipe)
- `ws/` is your colcon workspace. Edit it on the Mac (VS Code/Cursor); build it in the container.

## Install on a new Mac

```bash
curl -fsSL https://raw.githubusercontent.com/DavidSeyserGit/ros2-dev/main/install.sh | bash
```

This installs Homebrew (if missing), Colima and the Docker CLI tools, starts the VM, clones this repo to `~/ros2`, builds the image and opens the desktop.

## Daily use

`rosdev` works from any folder (the installer links it into Homebrew's `bin`).

```bash
rosdev up        # starts Colima VM + container, opens the browser desktop
rosdev shell     # terminal inside the container (ROS already sourced)
rosdev build     # colcon build --symlink-install in ws/
rosdev down      # stop the container
rosdev stop-vm   # also stop the Colima VM to free RAM
rosdev update    # pull latest repo, rebuild image, restart
rosdev uninstall # remove everything (asks before each step)
```

## MoveIt demo

Inside the desktop, double-click **MoveIt Panda Demo** (on first click XFCE asks you to trust the launcher).
Or run this in a container terminal:

```bash
ros2 launch arm_bringup moveit_demo.launch.py
```

In RViz → MotionPlanning → **Context** tab, pick the pipeline (`ompl`, `chomp`,
`pilz_industrial_motion_planner`, `stomp`). Then drag the goal marker and click **Plan** / **Plan & Execute**.

`ws/src/arm_bringup/launch/moveit_demo.launch.py` is a template: point `MoveItConfigsBuilder`
at your own `*_moveit_config` package to swap in your arm.

## Shell aliases (in the container)

| alias | does |
|---|---|
| `cb` | `colcon build --symlink-install` + source |
| `cbp <pkg>` | build selected packages |
| `rdi` | `rosdep install` deps for `ws/src` |
| `ct` | run tests |
| `panda` | stock Panda MoveIt demo |

## Notes

- Port 6080 is bound to `127.0.0.1` only, because the VNC desktop has no password.
- Screen size: `RESOLUTION=2560x1440 rosdev up`. The browser URL uses `resize=scale`, which shrinks the whole desktop to fit the window.
- The VM was created with `colima start --cpu 6 --memory 8 --disk 80 --vm-type vz --vz-rosetta`.
  To change it: `colima stop && colima start --cpu N --memory N`.
- Anything installed with `apt` inside a running container is lost on rebuild. Add it to the `Dockerfile` instead.
- To start Colima automatically at login: `brew services start colima`.
