# Changelog

## v0.2.0 — 2026-09-27

- Browser-based VS Code with Python and C++ language support on port 8080
- `rosdev new` package scaffolding for Python and C++, including a publisher and launch file
- `rosdev top` live node, topic-rate, CPU and RAM overview
- Workspace management with `rosdev ws list` and `rosdev ws use`
- Optional add-on system with the Foxglove bridge on `ws://localhost:8765`
- Foxglove asset access for `package://` resources and meshes in the mounted workspace

## v0.1.0 — 2026-09-25

First public release.

- ROS 2 Jazzy + MoveIt 2.12 container, native arm64 on Apple Silicon (amd64 works too)
- Browser desktop: XFCE + TigerVNC + noVNC on `localhost:6080`, software OpenGL (llvmpipe)
- MoveIt planning pipelines: OMPL, CHOMP, Pilz industrial, STOMP
- `arm_bringup` demo launch template (Panda)
- Terminal-only Docker via Colima, no Docker Desktop
- One-line installer with TUI (`install.sh`)
- Global `rosdev` command: `up`, `shell`, `build`, `doctor`, `update`, `uninstall`, …
- VS Code / Cursor Dev Container config
- `CLAUDE.md` so coding agents know how to build and run inside the container
