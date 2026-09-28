#!/bin/bash
# Shared by rosdev build, cb and cbp; run in a shell with ROS already sourced.
set -euo pipefail
cd ~/ws

cmake_args=(-DCMAKE_EXPORT_COMPILE_COMMANDS=ON --no-warn-unused-cli)
if command -v ccache >/dev/null 2>&1; then
  cmake_args+=(-DCMAKE_C_COMPILER_LAUNCHER=ccache -DCMAKE_CXX_COMPILER_LAUNCHER=ccache)
fi

# Put defaults before user CMake options, so explicit overrides keep working.
args=(--symlink-install)
has_cmake_args=false
build_base=build
next_build_base=false
for arg in "$@"; do
  if "$next_build_base"; then
    build_base=$arg
    next_build_base=false
  fi
  case "$arg" in
    --cmake-args)
      args+=(--cmake-args "${cmake_args[@]}")
      has_cmake_args=true
      ;;
    --cmake-args=*)
      args+=(--cmake-args "${cmake_args[@]}" "${arg#*=}")
      has_cmake_args=true
      ;;
    --build-base)
      args+=("$arg")
      next_build_base=true
      ;;
    --build-base=*)
      args+=("$arg")
      build_base=${arg#*=}
      ;;
    *) args+=("$arg") ;;
  esac
done
if ! "$has_cmake_args"; then
  args+=(--cmake-args "${cmake_args[@]}")
fi

colcon build "${args[@]}"

# Build artifacts can live in a separate mounted volume; keep the database there.
mkdir -p "$build_base"
shopt -s nullglob
databases=("$build_base"/*/compile_commands.json)
if [ "${#databases[@]}" -gt 0 ]; then
  jq -s 'add // []' "${databases[@]}" > "$build_base/compile_commands.json"
else
  printf '[]\n' > "$build_base/compile_commands.json"
fi
