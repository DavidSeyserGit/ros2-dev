# Changelog

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
