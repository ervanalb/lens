#!/bin/sh

ffmpeg -f h264 -i "$1" \
    -f h264 -i - \
    -filter_complex "[0:v] colorkey=#FFFFFF:0.1:0.5 [trv], [1:v] [trv] overlay=$2:$3" \
    -f h264 -
