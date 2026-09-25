# ROS 2 Jazzy + MoveIt 2 dev container with a browser desktop (noVNC on :6080).
# Native arm64 on Apple Silicon; RViz renders in software via Mesa llvmpipe.
FROM ros:jazzy

ARG USERNAME=ros
ARG USER_UID=1000
ARG USER_GID=1000
ENV DEBIAN_FRONTEND=noninteractive \
    LANG=C.UTF-8 \
    LC_ALL=C.UTF-8 \
    TZ=Europe/Zurich

# Desktop: TigerVNC X server + XFCE + noVNC, plus Mesa for software OpenGL
RUN apt-get update && apt-get install -y --no-install-recommends \
      tigervnc-standalone-server tigervnc-tools \
      novnc websockify supervisor \
      xfce4 xfce4-terminal xfce4-taskmanager thunar mousepad \
      dbus-x11 x11-xserver-utils xdg-utils \
      libgl1 libglx-mesa0 libgl1-mesa-dri mesa-utils \
      fonts-dejavu fonts-ubuntu adwaita-icon-theme-full \
      sudo git curl wget vim nano less htop tree tmux gdb ca-certificates \
      build-essential cmake python3-pip python3-venv \
      python3-colcon-common-extensions python3-colcon-mixin python3-rosdep python3-vcstool \
    && rm -rf /var/lib/apt/lists/*

# ROS desktop (RViz, rqt, demos) + MoveIt with all planners (OMPL, CHOMP, Pilz, STOMP)
RUN apt-get update && apt-get install -y --no-install-recommends \
      ros-jazzy-desktop \
      ros-jazzy-moveit \
      ros-jazzy-moveit-planners \
      ros-jazzy-moveit-planners-stomp \
      ros-jazzy-moveit-planners-chomp \
      ros-jazzy-pilz-industrial-motion-planner \
      ros-jazzy-moveit-py \
      ros-jazzy-moveit-servo \
      ros-jazzy-moveit-visual-tools \
      ros-jazzy-moveit-resources \
      ros-jazzy-moveit-resources-panda-moveit-config \
      ros-jazzy-moveit-setup-assistant \
      ros-jazzy-ros2-control ros-jazzy-ros2-controllers \
      ros-jazzy-xacro ros-jazzy-joint-state-publisher-gui \
      ros-jazzy-rmw-cyclonedds-cpp \
    && rm -rf /var/lib/apt/lists/*

# Non-root user (replace the stock "ubuntu" user that owns UID 1000 on noble)
RUN (userdel -r ubuntu 2>/dev/null || true) \
    && groupadd --gid ${USER_GID} ${USERNAME} \
    && useradd --uid ${USER_UID} --gid ${USER_GID} -m -s /bin/bash ${USERNAME} \
    && echo "${USERNAME} ALL=(ALL) NOPASSWD:ALL" > /etc/sudoers.d/${USERNAME} \
    && chmod 0440 /etc/sudoers.d/${USERNAME}

COPY docker/supervisord.conf /etc/supervisor/desktop.conf
COPY docker/entrypoint.sh /usr/local/bin/entrypoint.sh
COPY docker/skel/ /home/${USERNAME}/
RUN chmod +x /usr/local/bin/entrypoint.sh \
    && ln -sf /usr/share/novnc/vnc.html /usr/share/novnc/index.html \
    && sed -i '1i source ~/.bash_ros  # before the interactive-only guard so exec/login shells get ROS too' /home/${USERNAME}/.bashrc \
    && cp /etc/xdg/xfce4/panel/default.xml /home/${USERNAME}/.config/xfce4/xfconf/xfce-perchannel-xml/xfce4-panel.xml \
    && chown -R ${USERNAME}:${USERNAME} /home/${USERNAME}

USER ${USERNAME}
WORKDIR /home/${USERNAME}/ws
RUN rosdep update --rosdistro jazzy

ENV DISPLAY=:1 \
    LIBGL_ALWAYS_SOFTWARE=1 \
    GALLIUM_DRIVER=llvmpipe \
    RESOLUTION=1920x1080 \
    RMW_IMPLEMENTATION=rmw_cyclonedds_cpp

EXPOSE 6080
ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
