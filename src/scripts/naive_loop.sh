#!/bin/sh

TIMESTAMP_W=123
TIMESTAMP_H=12
TIMESTAMP_X=${TIMESTAMP_W}+1
TIMESTAMP_Y=17

ffmpeg -f h264 -i "$1" -f h264 -i - \
    -filter_complex "[0:v] overlay" \
    -f h264 -
