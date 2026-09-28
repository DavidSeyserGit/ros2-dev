# Changelog

## Unreleased — native Apple container branch

- `rosdev test`: build and test in a private ROS domain with a time limit, optional
  memory cap, GoogleTest filter, and a failures-only (or `--json`) summary
- Background jobs: `rosdev launch`, `rosdev start`, `rosdev jobs`, `rosdev logs NAME`,
  `rosdev stop`, replacing the manual `nohup` recipe
- `rosdev screenshot`: PNG of the desktop (optionally cropped/scaled) for agents
- Agent instructions (`CLAUDE.md`, workspace template) describe the new commands
- Apple `container` replaces Colima and Docker in the macOS installer and `rosdev`
- Apple Silicon / macOS 26+ required; Docker Compose remains an explicit alternative
- Reuse unchanged images and local additions instead of rebuilding on every start
- Browser editor starts on demand; new workspaces are empty and demos are removed
- Per-container CPU and memory settings in `.env`; preserve workspace and personal dependencies
- Run `rosdev rebuild` to use this branch's image changes; the published image is unchanged
- Linux volumes for build/install/log, persistent ccache, and leaner image build contexts
- Repeated native startup and filesystem measurements documented in PERFORMANCE.md
- RViz continues to render in software

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
