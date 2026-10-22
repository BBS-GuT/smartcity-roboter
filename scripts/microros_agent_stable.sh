#!/bin/bash
# Start the micro-ROS agent only after its stable serial device is available.
# Recovery retries belong to systemd; this script never resets or flashes hardware.
set -e

# Keep the agent environment close to Yahboom's original start script. In
# particular, do not inherit the project's Fast DDS profile intended for panel
# and camera traffic.
[ -f /opt/ros/humble/setup.bash ] && source /opt/ros/humble/setup.bash
workspace_root="${MICROROS_WORKSPACE_HOME:-$HOME}"
for workspace in "$workspace_root/yahboomcar_ws" "$workspace_root/mircoROS_agent"; do
    [ ! -f "$workspace/install/setup.bash" ] || source "$workspace/install/setup.bash"
done

export ROS_DOMAIN_ID="${ROS_DOMAIN_ID:-30}"
export ROS_LOCALHOST_ONLY="${ROS_LOCALHOST_ONLY:-0}"
export RMW_IMPLEMENTATION="${RMW_IMPLEMENTATION:-rmw_cyclonedds_cpp}"

unset FASTRTPS_DEFAULT_PROFILES_FILE
unset FASTDDS_DEFAULT_PROFILES_FILE
unset RMW_FASTRTPS_USE_QOS_FROM_XML
if [ -n "${MICROROS_FASTDDS_PROFILE:-}" ]; then
    export FASTRTPS_DEFAULT_PROFILES_FILE="$MICROROS_FASTDDS_PROFILE"
fi

DEVICE="${MICROROS_SERIAL_DEVICE:-/dev/myserial}"
WAIT_SECONDS="${MICROROS_DEVICE_WAIT_SECONDS:-30}"
DEADLINE=$((SECONDS + WAIT_SECONDS))

while [ ! -e "$DEVICE" ]; do
    if [ "$SECONDS" -ge "$DEADLINE" ]; then
        echo "micro-ROS serial device not available: $DEVICE" >&2
        exit 1
    fi
    sleep 0.25
done

exec "${MICROROS_ROS2:-ros2}" run micro_ros_agent micro_ros_agent serial \
    --dev "$DEVICE" \
    -b "${MICROROS_BAUD:-2000000}" \
    -v "${MICROROS_VERBOSITY:-4}"
