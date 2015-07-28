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
    print "Passing through traffic"

    tap = driver.FakeTap()

    loop, link_layer = ethernet.build_ethernet_loop()
    tap.mitm()

    eth_layer = ethernet.EthernetLayer()
    link_layer.register_child(eth_layer)

    try:
        loop.start()
    except:
        tap.passthru()

