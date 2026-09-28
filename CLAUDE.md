# ROS 2 dev environment

ROS 2 Jazzy + MoveIt 2 run in the `ros2` container using Apple's `container` CLI
on Apple Silicon / macOS 26+. ROS is not installed on the Mac.

- This repo contains the environment. User packages live in the workspace
  (`rosdev ws` prints it; `ROS2_WS` in `.env`), mounted at `/home/ros/ws`.
  Workspaces start empty. Do not add demo projects.
- `build/`, `install/`, `log/`, and compiler caches use persistent Linux volumes;
  inspect those inside the container, not on the Mac.
- Run ROS commands with `./rosdev exec '<cmd>'` from this repo, or the global
  `rosdev` command from any directory. ROS and workspace `install/` are sourced.
- Build: `./rosdev build`; select packages with `./rosdev build --packages-select <pkg>`.
- Dependencies: `./rosdev exec 'cd ~/ws && rosdep install --from-paths src --ignore-src -r -y'`.
- Tests: `./rosdev test [<pkg>...]` builds, runs `colcon test` in a private
  `ROS_DOMAIN_ID`, and prints only failures. Options: `--filter '<gtest filter>'`,
  `--timeout <s>`, `--mem 4G`, `--no-build`, `--json`. Exit code 0 = passed,
  124 = time limit reached.
- Background launches: `./rosdev launch <name> <pkg> <file> [args]` (or
  `./rosdev start <name> '<cmd>'`); then `./rosdev jobs`, `./rosdev logs <name> [-n N]`,
  `./rosdev stop <name>`. Stop jobs you started when you are done.
- See the desktop: `./rosdev screenshot [file.png] [--region X,Y,W,H] [--scale 0.5]`
  saves a PNG and prints its path; read that image to check RViz or other GUIs.
- `./rosdev up` starts the desktop at http://localhost:6080. `DISPLAY=:1` is set.
  `./rosdev code` starts the browser editor on demand.
- Use `ros-jazzy-*` apt packages. Generic environment dependencies belong in
  `Dockerfile`; personal/project dependencies belong in git-ignored
  `local/Dockerfile`. Do not rely on interactive apt installs persisting.
- `./rosdev rebuild` builds this checkout's Dockerfile locally. The published
  image does not acquire branch changes until it is rebuilt and published.
- `compose.yaml` and `.devcontainer/` are for explicit legacy Docker use only.
  Native `rosdev` commands never manage Docker or Colima.
