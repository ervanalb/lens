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
    addr = "192.168.0.15"
    alice_nic = "enp0s20u3"
    bob_nic =   "enp0s20u4"

    print "Passing through TCP traffic to IP", addr

    tap = driver.FakeTap()

    loop, link_layer = ethernet.build_ethernet_loop(alice_nic, bob_nic)
    tap.mitm()

    eth_layer = ethernet.EthernetLayer()
    link_layer.register_child(eth_layer)

    ipv4_layer = ip.IPv4Layer(addr_filter=[addr])
    eth_layer.register_child(ipv4_layer, dpkt.ethernet.ETH_TYPE_IP)

    tcp_layer = tcp.TCPLayer(debug=True)
    ipv4_layer.register_child(tcp_layer, dpkt.ip.IP_PROTO_TCP)

    try:
        loop.start()
    except:
        tap.passthru()

