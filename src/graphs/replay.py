#!/usr/bin/python2

import base
import ethernet 
import http
import ip
import rtp
import tcp
import udp
import util
import video

eth_layer = ethernet.EthernetLayer()
root.register_child(eth_layer)

ipv4_layer = ip.IPv4Layer()
eth_layer.register_child(ipv4_layer)

#ipv4_filter_layer = ip.IPv4FilterLayer(ips=addr)
#ipv4_layer.register_child(ipv4_filter_layer)
ipv4_filter_layer = ipv4_layer

udp_layer = udp.UDPLayer()
ipv4_filter_layer.register_child(udp_layer)

tcp_layer = tcp.TCPLayer()
ipv4_filter_layer.register_child(tcp_layer)

rtsp_filter_layer = tcp.TCPFilterLayer(554)
rtsp_filter_layer.name = "rtsp_port_filter"
tcp_layer.register_child(rtsp_filter_layer)

rtsp_lbf_layer = util.LineBufferLayer()
rtsp_filter_layer.register_child(rtsp_lbf_layer)

rtsp_layer = rtp.RTSPLayer(debug=True)
rtsp_lbf_layer.register_child(rtsp_layer)

video_filter_layer = udp.UDPFilterLayer(40000)
video_filter_layer.name = "video_port_filter"
udp_layer.register_child(video_filter_layer)

video_layer = video.H264NalLayer()
video_filter_layer.register_child(video_layer)

recorder_layer = util.RecorderLayer()
video_layer.register_child(recorder_layer)

ffmpeg_layer = video.FfmpegLayer("sh", "scripts/haxed_loop.sh", "loop:hack.h264")
recorder_layer.register_child(ffmpeg_layer)
