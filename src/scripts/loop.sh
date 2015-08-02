#!/bin/sh

ffmpeg -f h264 -i - -f h264 -i "$1" -filter_complex "overlay" -f h264 -
