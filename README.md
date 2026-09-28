# ROS 2 Jazzy + MoveIt 2

A complete ROS 2 development environment with a browser desktop, RViz, Python,
C++, and MoveIt planning pipelines (OMPL, CHOMP, Pilz, STOMP). Packages live in an
empty workspace on your Mac. No demo projects are installed.

The native backend uses [Apple's `container`](https://github.com/apple/container)
on **Apple Silicon with macOS 26 or later**. Linux runs in a lightweight virtual
machine for each container. RViz still uses software rendering (Mesa llvmpipe);
this migration does not enable GPU acceleration. See [measurements and their
limits](PERFORMANCE.md) for the startup and filesystem results.

## Use this branch

From a checkout of `perf/apple-container`:

```bash
brew install container git
container system start --enable-kernel-install
./rosdev rebuild
```

This uses `ROS2_WS` from `.env`, or `./ws` if unset. Set it to your existing
workspace to keep using your packages.

Once this branch is published, new Macs can use the installer:

```bash
curl -fsSL https://raw.githubusercontent.com/DavidSeyserGit/ros2-dev/perf/apple-container/install.sh \
  | ROS2_DEV_BRANCH=perf/apple-container bash
rosdev rebuild
```

The installer installs Homebrew if needed, then `container` and Git, clones the
environment to `~/ros2`, creates `~/ros2_ws/src`, and starts the desktop at
http://localhost:6080. Set `ROS2_OPEN_BROWSER=0` on the installer command to skip
opening the browser. It preserves existing `.env`, `local/`, and workspace files.
An existing clone must be clean and on the requested branch; the installer never
switches it automatically. `ROS2_DEV_BRANCH` defaults to `main`.

**The published image is unchanged.** `rosdev up` downloads it if absent and
reuses it afterward. Run `rosdev rebuild` to build this branch's image changes
locally, including the leaner desktop startup and removal of bundled demos.

Stop any existing Docker/Colima `ros2` container first so its ports are free:
`docker compose down` from the old environment directory. Existing workspace
files and `local/Dockerfile` can be reused. A previous Colima VM can be stopped
with `colima stop` when it is no longer needed.

## Daily use

The installer links `rosdev` into Homebrew's `bin`, so it works from any folder.
When using a checkout directly, run `./rosdev` from that directory.

```bash
rosdev up                    # start services and desktop; reuse unchanged images
rosdev shell                 # shell with ROS and your workspace sourced
rosdev code                  # start the browser editor on demand, then open it
rosdev exec 'ros2 topic list' # run a command inside the container
rosdev build                 # build the workspace with colcon
rosdev ws                    # print the active workspace path
rosdev ws use ~/another_ws   # switch workspace; create empty src/ if needed
rosdev down                  # stop the ROS container
rosdev stop-vm               # stop the ROS container and image builder
rosdev doctor                # check runtime, image, workspace, and desktop
```

`rosdev new`, `top`, and optional `addon` commands remain available. Run `rosdev`
for the full command list. Nothing is generated in a workspace until requested.
`rosdev update` updates the checkout and image; `rosdev rebuild` builds the image
from your current checkout. Use `rebuild` after changing the main Dockerfile or
to test unpublished image changes on this branch.

## Settings and persistent files

| Location | Purpose |
|---|---|
| `~/ros2` | Environment checkout; keep your packages outside it. |
| `~/ros2_ws/src` | Your packages and repositories, mounted at `/home/ros/ws`. |
| `~/ros2/.env` | Workspace, container resources, and image selection. |
| `~/ros2/local/Dockerfile` | Optional persistent dependencies; template in `local.example/`. |

Source files stay on your Mac. Build output (`build/`, `install/`, `log/`) and the
compiler cache use persistent Linux volumes for each workspace, avoiding shared
filesystem overhead during compilation. They survive container recreation and
workspace switching. Existing build output on the Mac is left untouched; run
`rosdev build` after migrating a workspace. The native build output is visible
inside the container, including in the browser editor.

Example `.env`:

```dotenv
ROS2_WS=/Users/you/ros2_ws
ROS2_CPUS=6
ROS2_MEMORY=8G
RESOLUTION=1920x1080
ROS_DOMAIN_ID=0
```

If the native runtime cannot resolve package servers on your network, set
`ROS2_DNS` to a reachable DNS server in `.env` and run `rosdev up` again. The same
setting is passed to image builds.

Run `rosdev up` after changing settings. Optional `ROS2_DEV_TAG` selects a
published version; `ROS2_DEV_IMAGE` selects a complete image reference.
Explicit image settings take precedence over a remembered local build on the
next `up`; remove them to keep using this checkout's rebuilt image.
`local/Dockerfile`, when present, extends the selected image. Its build is reused
until its inputs change. Packages installed interactively with `apt` disappear
when the container is recreated; put permanent additions in that Dockerfile.
`.env` and `local/` are git-ignored.

The desktop (6080) and browser editor (8080) are published on `127.0.0.1` on the
Mac. Their unauthenticated services are also reachable at the container's IP
from the Mac and other containers on the same virtual network. Loopback port
publishing does not isolate that address. The editor starts with `rosdev code`.

Shell helpers include `cb` (build and source), `cbp` (build selected packages),
`rdi` (install workspace dependencies), and `ct` (run tests).

ROS discovery between processes in this container is supported. Automatic
discovery of physical robots on your LAN has not been validated: Apple's native
network uses NAT and does not provide a bridged LAN interface. Static DDS peers
also require bidirectional network reachability.

## Docker and Dev Containers

`compose.yaml` remains available for explicit Docker use on Linux or an existing
Docker setup. The native `rosdev` commands use Apple's CLI and do not manage
Docker. Do not run both backends on the same ports.

```bash
docker compose up -d --build
docker compose exec ros2 bash -l
docker compose down
```

VS Code / Cursor **Dev Containers: Reopen in Container** uses the Docker Compose
configuration in `.devcontainer/`. It requires a separately installed Docker
runtime and does not attach to the Apple container. For the native backend, edit
files on your Mac or use `rosdev code`.

MIT, see [LICENSE](LICENSE).
