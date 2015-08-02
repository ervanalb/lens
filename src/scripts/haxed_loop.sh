#!/bin/sh

TIMESTAMP_W=123
TIMESTAMP_H=12
TIMESTAMP_X=${TIMESTAMP_W}+1
TIMESTAMP_Y=17

ffmpeg -f h264 -i "$1" \
    -vf "negate=enable=lt(mod(t\,2)\,1), \
    drawtext=text='you are being haxed':fontcolor=red:fontsize=30:x=(main_w-text_w)/2:y=100:enable=lt(mod(t\,0.3)\,0.15), \
    drawtext=text='lol gg':fontcolor=red:fontsize=30:x=(main_w-text_w)/2:y=140:enable=lt(mod(t\,0.9)\,0.6)" \
    -f h264 -i -
    -filter_complex "[0:v] overlay" \
    -f h264 -
