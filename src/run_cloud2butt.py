#!/usr/bin/python2
import dpkt
import driver

import base
import ethernet 
import ip
import tcp
import udp
import http

import tornado.gen as gen

from base import l, connect, NetLayer

if __name__ == "__main__":
    print "Cloud 2 butt: s/cloud/butt/g over HTTP"

    tap = driver.FakeTap()

    loop, link_layer = ethernet.build_ethernet_loop()
    tap.mitm()

    eth_layer = ethernet.EthernetLayer()
    link_layer.register_child(eth_layer)

    #ipv4_layer = ip.IPv4Layer(addr_filter=["192.168.1.10"])
    ipv4_layer = ip.IPv4Layer(addr_filter=None)
    eth_layer.register_child(ipv4_layer, dpkt.ethernet.ETH_TYPE_IP)

    tcp_layer = tcp.TCPLayer(debug=True)
    ipv4_layer.register_child(tcp_layer, dpkt.ip.IP_PROTO_TCP)

    http_lbf_layer = base.LineBufferLayer()
    tcp_layer.register_child(http_lbf_layer, 8000)
    tcp_layer.register_child(http_lbf_layer, 80)

    http_layer = http.HTTPLayer()
    http_lbf_layer.register_child(http_layer)

    c2b_layer = base.CloudToButtLayer()
    http_layer.register_child(c2b_layer, "text")

    try:
        loop.start()
    except:
        tap.passthru()

