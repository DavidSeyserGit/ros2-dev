#!/usr/bin/env bash
# One-shot setup of the ROS 2 Jazzy + MoveIt browser-desktop env on a Mac.
#   curl -fsSL https://raw.githubusercontent.com/DavidSeyserGit/ros2-dev/main/install.sh | bash
set -euo pipefail

REPO="${ROS2_DEV_REPO:-https://github.com/DavidSeyserGit/ros2-dev.git}"
DIR="${ROS2_DEV_DIR:-$HOME/ros2}"
CPUS="${COLIMA_CPUS:-6}"; MEM="${COLIMA_MEM:-8}"; DISK="${COLIMA_DISK:-80}"

say() { printf '\n\033[1;34m==> %s\033[0m\n' "$*"; }

[ "$(uname -s)" = Darwin ] || { echo "macOS only (on Linux: install Docker Engine, clone the repo, docker compose up -d)"; exit 1; }

if ! command -v brew >/dev/null; then
  say "Installing Homebrew"
  /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
  eval "$(/opt/homebrew/bin/brew shellenv 2>/dev/null || /usr/local/bin/brew shellenv)"
fi

say "Installing colima, docker CLI, compose, buildx, git"
brew install colima docker docker-compose docker-buildx git

say "Configuring docker CLI plugins"
mkdir -p ~/.docker
CFG=~/.docker/config.json
[ -f "$CFG" ] || echo '{}' > "$CFG"
/usr/bin/python3 - "$CFG" "$(brew --prefix)/lib/docker/cli-plugins" <<'PY'
import json, sys
p, d = sys.argv[1], sys.argv[2]
c = json.load(open(p))
dirs = c.setdefault("cliPluginsExtraDirs", [])
if d not in dirs: dirs.append(d)
if c.get("credsStore") == "desktop" and not __import__("shutil").which("docker-credential-desktop"):
    c.pop("credsStore")
json.dump(c, open(p, "w"), indent=2)
PY

if ! colima status >/dev/null 2>&1; then
  say "Starting Colima VM (${CPUS} CPU, ${MEM} GB RAM, ${DISK} GB disk)"
  ARCH_FLAGS=(); [ "$(uname -m)" = arm64 ] && ARCH_FLAGS=(--vm-type vz --vz-rosetta --mount-type virtiofs)
  colima start --cpu "$CPUS" --memory "$MEM" --disk "$DISK" "${ARCH_FLAGS[@]}"
fi
docker context use colima >/dev/null

if [ -d "$DIR/.git" ]; then
  say "Updating $DIR"; git -C "$DIR" pull --ff-only
else
  say "Cloning into $DIR"; git clone "$REPO" "$DIR"
fi

say "Building image and starting container (first build ~10 min)"
cd "$DIR" && ./rosdev up

say "Done. Desktop: http://localhost:6080  —  shell: cd $DIR && ./rosdev shell"
