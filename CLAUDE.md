# ROS 2 dev environment

ROS 2 **Jazzy** + MoveIt 2 run inside the Docker container `ros2` (Colima VM, arm64). ROS is NOT installed on the Mac.

- Code lives in `ws/src/` on the Mac, which is bind-mounted to `/home/ros/ws` in the container. Edit files on the Mac as usual.
- Run every ROS command inside the container, from this directory:
  `docker compose exec ros2 bash -lc '<cmd>'` (ROS and ws/install are sourced automatically)
- Build: `docker compose exec ros2 bash -lc 'cd ~/ws && colcon build --symlink-install'`
  (one package: add `--packages-select <pkg>`)
- Deps: `docker compose exec ros2 bash -lc 'cd ~/ws && rosdep install --from-paths src --ignore-src -r -y'`
- Tests: `docker compose exec ros2 bash -lc 'cd ~/ws && colcon test && colcon test-result --verbose'`
- Long-running nodes/launches: start detached so they don't block, and log to a file:
  `docker compose exec -d ros2 bash -lc 'ros2 launch <pkg> <file> > /tmp/<name>.log 2>&1'`
  then inspect with `docker compose exec ros2 bash -lc 'tail -50 /tmp/<name>.log'`.
  GUI apps (RViz) appear on the browser desktop at http://localhost:6080 (DISPLAY=:1 is preset).
- If the container is not running: `./rosdev up`.
- Use `ros-jazzy-*` apt packages. Permanent system deps belong in `Dockerfile`, not ad-hoc apt installs.
- `ws/src/arm_bringup` = MoveIt demo launch template (OMPL, CHOMP, Pilz, STOMP pipelines).
