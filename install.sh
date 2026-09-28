#!/usr/bin/env bash
# Install the native Apple container backend on an Apple Silicon Mac.
set -euo pipefail

REPO="${ROS2_DEV_REPO:-https://github.com/DavidSeyserGit/ros2-dev.git}"
BRANCH="${ROS2_DEV_BRANCH:-main}"
DIR="${ROS2_DEV_DIR:-$HOME/ros2}"
WS="${ROS2_WS:-${ROS2_WS_DIR:-$HOME/ros2_ws}}"
WS=${WS/#\~/$HOME}

fail() { printf 'Error: %s\n' "$*" >&2; exit 1; }
step() { printf '\n%s\n' "$*"; }

[ "$(uname -s)" = Darwin ] || fail 'This installer requires macOS. For Docker on Linux, use compose.yaml directly.'
[ "$(uname -m)" = arm64 ] || fail 'Apple Silicon is required for the native container backend.'
MACOS_VERSION=$(sw_vers -productVersion)
[ "${MACOS_VERSION%%.*}" -ge 26 ] || fail 'macOS 26 or later is required.'

if ! command -v brew >/dev/null 2>&1 && [ ! -x /opt/homebrew/bin/brew ]; then
  step 'Installing Homebrew (may request your password)...'
  NONINTERACTIVE=1 /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)" </dev/tty
fi
if [ -x /opt/homebrew/bin/brew ]; then
  eval "$(/opt/homebrew/bin/brew shellenv)"
fi

step 'Installing Apple container and Git...'
brew install container git

if [ -e "$DIR/.git" ]; then
  CURRENT_BRANCH=$(git -C "$DIR" symbolic-ref --quiet --short HEAD || true)
  [ "$CURRENT_BRANCH" = "$BRANCH" ] || fail \
    "$DIR is on '${CURRENT_BRANCH:-detached HEAD}', not '$BRANCH'. Set ROS2_DEV_BRANCH to that branch, or choose a new ROS2_DEV_DIR."
  [ -z "$(git -C "$DIR" status --porcelain)" ] || fail \
    "$DIR has uncommitted changes. Commit or stash them before running the installer again; use rosdev up for an existing setup."
  step "Updating $DIR ($BRANCH)..."
  git -C "$DIR" pull --ff-only origin "$BRANCH"
else
  step "Cloning $BRANCH into $DIR..."
  git clone --branch "$BRANCH" "$REPO" "$DIR"
fi
DIR=$(cd "$DIR" && pwd)

# Preserve existing settings and workspaces. No starter packages or local image
# layer are created; local/Dockerfile is only needed for personal dependencies.
if [ ! -f "$DIR/.env" ]; then
  mkdir -p "$WS/src"
  WS=$(cd "$WS" && pwd)
  export ROS2_WS="$WS"
  {
    printf 'ROS2_WS=%s\n' "$WS"
    printf 'ROS2_CPUS=%s\n' "${ROS2_CPUS:-6}"
    printf 'ROS2_MEMORY=%s\n' "${ROS2_MEMORY:-8G}"
    [ -z "${ROS2_DEV_TAG:-}" ] || printf 'ROS2_DEV_TAG=%s\n' "$ROS2_DEV_TAG"
    [ -z "${ROS2_DEV_IMAGE:-}" ] || printf 'ROS2_DEV_IMAGE=%s\n' "$ROS2_DEV_IMAGE"
    true
  } > "$DIR/.env"
fi
ln -sf "$DIR/rosdev" "$(brew --prefix)/bin/rosdev"
WS=$("$DIR/rosdev" ws)
mkdir -p "$WS/src"
[ -f "$WS/CLAUDE.md" ] || cp "$DIR/workspace.example/CLAUDE.md" "$WS/CLAUDE.md"

step 'Starting Apple container services...'
container system start --enable-kernel-install

step 'Starting ROS 2 (the first run downloads the image)...'
ROS2_OPEN_BROWSER="${ROS2_OPEN_BROWSER:-1}" "$DIR/rosdev" up

printf '\nReady.\n  Desktop:   http://localhost:6080\n  Workspace: %s/src\n  Shell:     rosdev shell\n  Editor:    rosdev code\n  Stop:      rosdev down\n' "$WS"
printf '\nTo use image changes from this checkout, run rosdev rebuild.\n'
