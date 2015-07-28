TIMESTAMP_W=123
TIMESTAMP_H=12
TIMESTAMP_X=${TIMESTAMP_W}+1
TIMESTAMP_Y=17

ffmpeg -i "$1" -f h264 -i - \
    -filter_complex "[1:v] crop=${TIMESTAMP_W}:${TIMESTAMP_H}:iw-(${TIMESTAMP_X}):${TIMESTAMP_Y}, [0:v] overlay=main_w-(${TIMESTAMP_X}):${TIMESTAMP_Y}" \
    -f h264 -
