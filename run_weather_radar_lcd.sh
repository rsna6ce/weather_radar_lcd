#!/bin/bash

# crontab delay
cd `dirname $0`
sleep 10s

# start script (if stopped auto restart)
while :
do
  python3 weather_radar_lcd.py
  sleep 1s
done
