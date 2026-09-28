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
- Tests: `rosdev exec 'cd ~/ws && colcon test && colcon test-result --verbose'`.
- Long-running launches can use
  `rosdev exec 'nohup ros2 launch <pkg> <file> > /tmp/<name>.log 2>&1 < /dev/null &'`;
  read the log with `rosdev exec 'tail -50 /tmp/<name>.log'`.
- `rosdev up` starts the desktop; `rosdev code` starts the browser editor on demand.
  GUI applications such as RViz appear on the desktop.
- Permanent system dependencies belong in `local/Dockerfile` inside the ros2-dev
  environment checkout. `rosdev ws` prints this workspace; `rosdev doctor` checks
  the setup. Do not add example packages unless requested.
