# Native container measurements

Measured on 2026-09-28: Apple Silicon Mac, macOS 27.0, Apple container 1.4.1.
Both environments received 6 CPUs and 8 GiB RAM. Colima and the native ROS
container ran separately; the image builder was stopped during measurements.

The file workload creates 2,000 files of 4 KiB each, then stats and reads them.
Numbers are medians of three samples. The original setup writes generated files
to a Mac workspace over VirtioFS; the native setup writes them to an ext4 volume.

| Operation | Colima / shared workspace | Native / ext4 volume | Ratio |
|---|---:|---:|---:|
| Write files | 1,169.7 ms | 23.4 ms | 50.0× |
| Stat files | 11.9 ms | 1.7 ms | 7.0× |
| Read files | 407.0 ms | 5.9 ms | 69.0× |
| Host CLI `exec true` | 77.9 ms | 55.9 ms | 1.4× |

Repeated `rosdev up` on an unchanged running native setup took **0.389 s**
(median of three samples; browser opening disabled). One stop/start cycle to
the desktop HTTP endpoint took **4.42 s**. A comparable cold-start or full
workspace-build baseline was not measured.

The isolated compiler-cache probe took 97.2 ms without a cached result and
1.28 ms with a cache hit. This probe compiles one small C++ translation unit;
it does not predict the speedup of a complete ROS package build.

These are buffered filesystem measurements, with no `fsync`; reads and stats
follow writes. They measure the combined runtime/storage change, not Apple's
runtime alone. They do not measure RViz frame rate, durable disk throughput,
large source trees, image download speed, or real robot latency. Source files
still use VirtioFS. RViz still uses software rendering.

## Reproduce

Use already running containers and existing writable directories. Each probe
creates and removes only its own temporary directory under the selected path.

```bash
# Run separately, with the competing VM and image builder stopped.
python3 tests/benchmark.py --docker-name ros2 > /tmp/docker-benchmark.json
python3 tests/benchmark.py --container-name ros2 > /tmp/native-benchmark.json

# After initial setup; this may start/reconfigure the selected environment.
python3 tests/benchmark.py \
  --up-command 'env ROS2_OPEN_BROWSER=0 ./rosdev up'
```

Live validation also covered image and local-overlay builds, a C++ ROS package
build, publisher/subscriber communication, software OpenGL, editor startup on
demand, and build/install/cache persistence across restarts. CLI regression tests
cover reuse, invalid settings, failed builds, workspace changes, and isolation
between checkouts without requiring a running container runtime.
