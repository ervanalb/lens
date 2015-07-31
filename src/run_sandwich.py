#!/usr/bin/python2
import dpkt
import driver

import shell

import base
import ethernet 
import ip
import tcp
import udp
import http
import video

import tornado.gen as gen

from base import l, connect, NetLayer

if __name__ == "__main__":
    #addr = ["192.168.1.10"]
    addr = []
    print "Capturing traffic to:", addr

    tap = driver.FakeTap()

    loop, link_layer = ethernet.build_ethernet_loop()
    tap.mitm()

    sh = shell.CommandShell()
    sh.ioloop_attach(loop)

    eth_layer = ethernet.EthernetLayer()
    sh.register_layer(eth_layer)
    link_layer.register_child(eth_layer)

    ipv4_layer = ip.IPv4Layer()
    sh.register_layer(ipv4_layer)
    eth_layer.register_child(ipv4_layer)

    #ipv4_filter_layer = ip.IPv4FilterLayer(ips=addr)
    #sh.register_layer(ipv4_filter_layer)
    #ipv4_layer.register_child(ipv4_filter_layer)
    ipv4_filter_layer = ipv4_layer

    udp_layer = udp.UDPLayer()
    sh.register_layer(udp_layer)
    ipv4_filter_layer.register_child(udp_layer)

    tcp_layer = tcp.TCPLayer(debug=False)
    sh.register_layer(tcp_layer)
    ipv4_filter_layer.register_child(tcp_layer)

    ssh_filter_layer = tcp.TCPFilterLayer(ports=[22])
    tcp_layer.register_child(ssh_filter_layer)

    http_filter_layer = tcp.TCPFilterLayer(ports=[80, 8000, 8080])
    sh.register_layer(http_filter_layer)
    tcp_layer.register_child(http_filter_layer)

    http_lbf_layer = base.LineBufferLayer()
    http_filter_layer.register_child(http_lbf_layer)

    print_layer = base.PrintLayer()
    http_lbf_layer.register_child(print_layer)
#
#    http_layer = http.HTTPLayer()
#    sh.register_layer(http_layer, "http")
#    http_lbf_layer.register_child(http_layer)
#
#    c2b_layer = base.CloudToButtLayer()
#    sh.register_layer(c2b_layer, "c2b")
#    http_layer.register_child(c2b_layer, "text")
#
#    img_layer = http.ImageFlipLayer()
#    http_layer.register_child(img_layer, "image")
#
#    xss_layer = http.XSSInjectorLayer()
#    sh.register_layer(xss_layer, "xss")
#    http_layer.register_child(xss_layer, "javascript")
#

    video_filter_layer = udp.UDPFilterLayer(ports=[40000])
    sh.register_layer(video_filter_layer)
    udp_layer.register_child(video_filter_layer)

    video_layer = video.H264NalLayer()
    sh.register_layer(video_layer)
    video_filter_layer.register_child(video_layer)
#
#    ffmpeg_layer = video.FfmpegLayer()
#    sh.register_layer(ffmpeg_layer, "ffmpeg")
#    video_layer.register_child(ffmpeg_layer)

    try:
        loop.start()
    except:
        tap.passthru()

