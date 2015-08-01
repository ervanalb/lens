#!/usr/bin/python2

import dpkt
import driver

import shell

import base
import link
import ethernet 
import ip
import tcp
import udp
import http
import video

import tornado.gen as gen
from tornado.ioloop import IOLoop

if __name__ == "__main__":
    #addr = ["192.168.1.10"]
    addr = []
    #print "Capturing traffic to:", addr

    tap = driver.FakeTap()

    link_layer = link.LinkLayer()

    tap.mitm()

    sh = shell.CommandShell()
    sh.available_layers = base.LayerMeta.layers.values()
    sh.ioloop_attach()

    eth_layer = ethernet.EthernetLayer()
    sh.register_layer_instance(eth_layer)
    link_layer.register_child(eth_layer)

    ipv4_layer = ip.IPv4Layer()
    sh.register_layer_instance(ipv4_layer)
    eth_layer.register_child(ipv4_layer)

    #ipv4_filter_layer = ip.IPv4FilterLayer(ips=addr)
    #sh.register_layer_instance(ipv4_filter_layer)
    #ipv4_layer.register_child(ipv4_filter_layer)
    ipv4_filter_layer = ipv4_layer

    udp_layer = udp.UDPLayer()
    sh.register_layer_instance(udp_layer)
    ipv4_filter_layer.register_child(udp_layer)

    tcp_layer = tcp.TCPLayer(debug=False)
    sh.register_layer_instance(tcp_layer)
    ipv4_filter_layer.register_child(tcp_layer)

    ssh_filter_layer = tcp.TCPFilterLayer(ports=[22])
    sh.register_layer_instance(ssh_filter_layer, "ssh_filter")
    tcp_layer.register_child(ssh_filter_layer)

    http_filter_layer = tcp.TCPFilterLayer(ports=[80, 8000, 8080])
    sh.register_layer_instance(http_filter_layer, "http_filter")
    tcp_layer.register_child(http_filter_layer)

    http_lbf_layer = base.LineBufferLayer()
    sh.register_layer_instance(http_lbf_layer)
    http_filter_layer.register_child(http_lbf_layer)

    #print_layer = base.PrintLayer()
    #http_lbf_layer.register_child(print_layer)

    http_layer = http.HTTPLayer()
    sh.register_layer_instance(http_layer)
    http_lbf_layer.register_child(http_layer)

    c2b_layer = http.CloudToButtLayer()
    sh.register_layer_instance(c2b_layer)
    http_layer.register_child(c2b_layer)

    img_layer = http.ImageFlipLayer()
    sh.register_layer_instance(img_layer)
    http_layer.register_child(img_layer)

    xss_layer = http.XSSInjectorLayer()
    sh.register_layer_instance(xss_layer)
    http_layer.register_child(xss_layer)

    video_filter_layer = udp.UDPFilterLayer(ports=[40000])
    sh.register_layer_instance(video_filter_layer, "video_filter")
    udp_layer.register_child(video_filter_layer)

    video_layer = video.H264NalLayer()
    sh.register_layer_instance(video_layer)
    video_filter_layer.register_child(video_layer)

    recorder_layer = base.RecorderLayer()
    sh.register_layer_instance(recorder_layer)
    video_layer.register_child(recorder_layer)

    ffmpeg_layer = video.FfmpegLayer(cmd="hack")
    sh.register_layer_instance(ffmpeg_layer)
    recorder_layer.register_child(ffmpeg_layer)

    try:
        IOLoop.instance().start()
    except:
        tap.passthru()
        raise
