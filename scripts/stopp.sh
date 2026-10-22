#!/bin/bash
# NOT-AUS: beendet den Linienfolger UND das Fahr-Gehirn und schickt Stopp an die Motoren.
source "$(dirname "$0")/env.sh"
# Fahr-Gehirn-Training: zuerst die Endlosschleife des Startskripts, sonst startet sie das Fahr-Gehirn neu
pkill -KILL -f fahrgehirn_training.sh
# Linienfolger / Fahr-Gehirn beenden (auch wenn vom Panel gestartet): erst sanft wie Strg+C, dann hart
pkill -INT -f "line_follower.py|fahrgehirn/fahrgehirn.py" && sleep 1
pkill -KILL -f "line_follower.py|fahrgehirn/fahrgehirn.py"
ros2 topic pub -t 5 -r 10 /cmd_vel geometry_msgs/msg/Twist "{}" > /dev/null
echo "Stopp gesendet."
