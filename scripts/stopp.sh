#!/bin/bash
# NOT-AUS: beendet den Linienfolger und schickt Stopp an die Motoren.
source "$(dirname "$0")/env.sh"
# Linienfolger beenden (auch wenn vom Panel gestartet): erst sanft wie Strg+C, dann hart
pkill -INT -f line_follower.py && sleep 1
pkill -KILL -f line_follower.py
ros2 topic pub -t 5 -r 10 /cmd_vel geometry_msgs/msg/Twist "{}" > /dev/null
echo "Stopp gesendet."
