# ROS 2 workspace

This is a colcon workspace used with **ros2-dev** (ROS 2 Jazzy + MoveIt 2 in a Docker
container, browser desktop at http://localhost:6080). ROS is NOT installed on the Mac.

- Packages live in `src/`. This folder is mounted into the container as `/home/ros/ws`;
  edit files here as usual.
- Run every ROS command in the container with `rosdev exec '<cmd>'` (ROS and
  install/ are sourced), from any folder:
  - build: `rosdev exec 'cd ~/ws && colcon build --symlink-install'`
  - one package: add `--packages-select <pkg>`
  - dependencies: `rosdev exec 'cd ~/ws && rosdep install --from-paths src --ignore-src -r -y'`
  - tests: `rosdev exec 'cd ~/ws && colcon test && colcon test-result --verbose'`
- Long-running launches: start them detached and log to a file, e.g.
  `rosdev exec 'nohup ros2 launch <pkg> <file> > /tmp/<name>.log 2>&1 &'`, then read the log.
  GUI apps (RViz) appear on the browser desktop.
- If the container is not running: `rosdev up`.
- System packages that should stay installed belong in `local/Dockerfile` of the
  ros2-dev folder (`rosdev ws` prints this workspace, `rosdev doctor` checks the setup).
