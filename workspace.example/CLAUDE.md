# ROS 2 workspace

This colcon workspace uses ros2-dev: ROS 2 Jazzy + MoveIt 2 in an Apple
container, with a browser desktop at http://localhost:6080. ROS is not installed
on the Mac.

- Packages belong in `src/`. This workspace is mounted at `/home/ros/ws`;
  edit its files on the Mac as usual.
- `build/`, `install/`, `log/`, and compiler caches use persistent Linux volumes;
  inspect those inside the container, not on the Mac.
- Run ROS commands with `rosdev exec '<cmd>'` from any folder. ROS and workspace
  `install/` are sourced automatically.
- Build: `rosdev build`; select packages with `rosdev build --packages-select <pkg>`.
- Dependencies: `rosdev exec 'cd ~/ws && rosdep install --from-paths src --ignore-src -r -y'`.
- Tests: `rosdev test [<pkg>...]` builds, runs `colcon test` in a private
  `ROS_DOMAIN_ID`, and prints only failures. Options: `--filter '<gtest filter>'`,
  `--timeout <s>`, `--mem 4G`, `--no-build`, `--json`. Exit code 0 = passed,
  124 = time limit reached.
- Background launches: `rosdev launch <name> <pkg> <file> [args]` (or
  `rosdev start <name> '<cmd>'`); then `rosdev jobs`, `rosdev logs <name> [-n N]`,
  `rosdev stop <name>`. Stop jobs you started when you are done.
- See the desktop: `rosdev screenshot [file.png] [--region X,Y,W,H] [--scale 0.5]`
  saves a PNG and prints its path; read that image to check RViz or other GUIs.
- `rosdev up` starts the desktop; `rosdev code` starts the browser editor on demand.
  GUI applications such as RViz appear on the desktop.
- Permanent system dependencies belong in `local/Dockerfile` inside the ros2-dev
  environment checkout. `rosdev ws` prints this workspace; `rosdev doctor` checks
  the setup. Do not add example packages unless requested.
