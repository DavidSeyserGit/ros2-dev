# Your additions to the ros2-dev image — copy this folder to local/ (git-ignored):
#   cp -r local.example local
# `rosdev up / rebuild / update` then build local/Dockerfile on top of the ros2-dev
# image automatically, so what you install here survives container restarts.
ARG BASE
FROM ${BASE}

USER root
# Example: extra ROS packages and Python modules
# RUN apt-get update && apt-get install -y --no-install-recommends \
#       ros-jazzy-ur-description \
#     && rm -rf /var/lib/apt/lists/*
# RUN pip3 install --no-cache-dir --break-system-packages some-module
USER ros
