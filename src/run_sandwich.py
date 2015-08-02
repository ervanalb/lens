#!/usr/bin/python2

import dpkt
import driver

import shell

import base
import ethernet 
import http
import ip
import link
import rtp
import tcp
import udp
import util
import video

import tornado.gen as gen
from tornado.ioloop import IOLoop

if __name__ == "__main__":
    tap = driver.FakeTap()
    tap.mitm()

    link_layer = link.LinkLayer()
    sh = shell.CommandShell(link_layer)

    eth_layer = ethernet.EthernetLayer()
    link_layer.register_child(eth_layer)

    ipv4_layer = ip.IPv4Layer()
    eth_layer.register_child(ipv4_layer)

    #ipv4_filter_layer = ip.IPv4FilterLayer(ips=addr)
    #ipv4_layer.register_child(ipv4_filter_layer)
    ipv4_filter_layer = ipv4_layer

    udp_layer = udp.UDPLayer()
    ipv4_filter_layer.register_child(udp_layer)

    tcp_layer = tcp.TCPLayer()
    ipv4_filter_layer.register_child(tcp_layer)

    ssh_filter_layer = tcp.TCPFilterLayer(ports=[22])
    ssh_filter_layer.name = "ssh_port_filter"
    tcp_layer.register_child(ssh_filter_layer)

    rtsp_filter_layer = tcp.TCPFilterLayer(ports=[554])
    rtsp_filter_layer.name = "rtsp_port_filter"
    tcp_layer.register_child(rtsp_filter_layer)

    rtsp_lbf_layer = util.LineBufferLayer()
    rtsp_filter_layer.register_child(rtsp_lbf_layer)

    rtsp_layer = rtp.RTSPLayer(debug=True)
    rtsp_lbf_layer.register_child(rtsp_layer)

    http_filter_layer = tcp.TCPFilterLayer(ports=[80, 8000, 8080])
    http_filter_layer.name = "http_port_filter"
    tcp_layer.register_child(http_filter_layer)

    http_lbf_layer = util.LineBufferLayer()
    http_filter_layer.register_child(http_lbf_layer)

    #print_layer = util.PrintLayer()
    #http_lbf_layer.register_child(print_layer)

    http_layer = http.HTTPLayer()
    http_lbf_layer.register_child(http_layer)

    c2b_layer = http.CloudToButtLayer()
    #http_layer.register_child(c2b_layer)

    img_layer = http.ImageFlipLayer()
    http_layer.register_child(img_layer)

    xss_layer = http.XSSInjectorLayer()
    http_layer.register_child(xss_layer)

    vim_layer = util.VimLayer()
    http_layer.register_child(vim_layer)

    video_filter_layer = udp.UDPFilterLayer(ports=[40000])
    video_filter_layer.name = "video_port_filter"
    udp_layer.register_child(video_filter_layer)

    video_layer = video.H264NalLayer()
    video_filter_layer.register_child(video_layer)

    recorder_layer = util.RecorderLayer()
    video_layer.register_child(recorder_layer)

    #ffmpeg_layer = video.FfmpegLayer(cmd="hack", debug=True)
    #recorder_layer.register_child(ffmpeg_layer)

    try:
        IOLoop.instance().start()
    finally:
        tap.passthru()
