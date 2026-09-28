# Native container measurements

Updated 2026-09-28 after running both complete setups sequentially on the same
Apple Silicon Mac (macOS 27.0, Apple container 1.4.1). The competing VM and image
builder were stopped for each run. Both setups were configured for 6 CPUs and
8 GiB RAM, with the desktop, Foxglove and browser editor running. Apple exposes
one additional overhead CPU to Linux; compiler concurrency was explicitly
limited to six jobs on both setups.

## Real package builds

The same `stiffness_planner` sources, including its C++ test executable, were
built three times per setup. Source hashes, GCC 13.3.0 versions, and installed
MoveIt core/OMPL versions matched. Each repetition used fresh temporary build,
install, log and compiler-cache directories. Normal workspace artifacts and
caches were preserved. Only `/opt/ros/jazzy/setup.bash` was sourced.

Medians from the initial three repetitions:

| Operation | Docker / Colima | Native Apple container |
|---|---:|---:|
| Fresh build, empty build/compiler caches | 24.13 s | 34.77 s |
| Clear objects and recompile | 21.18 s | 2.70 s |
| Unchanged build | 1.86 s | 0.51 s |

Docker used its existing configuration without a compiler cache. Native used
ccache and Linux ext4 output storage. Clearing objects was performed outside
the timer with `cmake --build <temporary-build>/stiffness_planner --target clean`.
The warm native runs produced 11 direct cache hits. This is a comparison of the
complete configurations, not of the runtimes alone. These tests built the test
executable; they did not run the planner's test suite.

**Fresh-build results are variable.** After restoring the native environment,
one control run with the original ccache mode took 18.95 s for the fresh build
and 1.40 s for recompilation. Separate single-run probes took 20.34 s without
ccache and 20.02 s with its dependency mode (1.42 s for cached recompilation).
These follow-ups do not establish a benefit from changing cache mode, and no
cache-mode setting was changed. They also mean the initial 34.77 s result cannot
support a general claim that native fresh builds are slower. System load and
OS caches were not controlled closely enough to claim a consistent fresh-build
speedup either. Empty compiler caches do not imply empty OS caches.

The repeated initial measurements support roughly 7.8× faster cached object
rebuilds and 3.7× faster unchanged builds for this package/configuration.

## Filesystem and startup

The file workload writes 2,000 files of 4 KiB each, then stats and reads them.
These updated medians use five samples per setup and supersede the earlier
three-sample microbenchmark. Outputs use VirtioFS on Docker and ext4 on native.

| Operation | Docker / Colima | Native Apple container |
|---|---:|---:|
| Write files | 387.04 ms | 29.52 ms |
| Stat files | 46.93 ms | 2.09 ms |
| Read files | 262.12 ms | 7.77 ms |
| Host CLI `exec true` | 34.85 ms | 62.39 ms |

File writes were 13.1× faster and reads 33.7× faster in this run. CLI process
execution was slower on native. These are buffered measurements without `fsync`;
reads and stats follow writes. They do not measure durable disk throughput.
Source files still use VirtioFS on both setups.

One startup observation with images already present: Colima VM startup took
13.11 s, followed by 1.67 s from Docker container start to the desktop HTTP
endpoint (14.78 s combined). Native container startup to that endpoint took
3.46 s, with Apple's host service already running. Editor readiness was not
included. These are single observations, not startup medians. The earlier
unchanged `rosdev up` measurement was 0.389 s (three-sample median, browser
opening disabled).

RViz frame rate and planning latency were not instrumented. The user reports
smooth 30 FPS after migration; RViz still uses software rendering.

## Reproduce and inspect

Run the file probe separately against already running containers, with the
competing VM stopped:

```bash
python3 tests/benchmark.py --docker-name ros2 --repeats 5
python3 tests/benchmark.py --container-name ros2 --repeats 5
```

The real-build probe used `colcon build --packages-select stiffness_planner`,
`--executor sequential`, `--symlink-install`, `BUILD_TESTING=ON`, and an empty
build type, with `MAKEFLAGS=-j6` and `CMAKE_BUILD_PARALLEL_LEVEL=6`. All paths for
build/install/log were inside a disposable directory under the corresponding
workspace's `build/`. Native set both CMake compiler launchers to `ccache` and
used an isolated `CCACHE_DIR`; Docker set both launchers to empty values.

Local raw results and the orchestration scripts are retained under
`local/.rosdev/benchmarks/`; `latest-path` identifies this run. That directory is
git-ignored. Temporary guest build trees were removed. The native container and
browser editor were restored, and Colima was stopped afterward.
