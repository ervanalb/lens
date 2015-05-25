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
    #addr = "18.238.0.97"
    addr = "192.168.1.10"
    print "Capturing traffic to:", addr

    tap = driver.Tap()

    loop, link_layer = ethernet.build_ethernet_loop()
    tap.mitm()

    stateless_layers = connect(
        link_layer, [
        l(ethernet.EthernetLayer),
        l(ip.IPv4Layer, addr_filter=[addr]),
        l(udp.UDPLayer),
        l(tcp.TCPPassthruLayer, ports=[22]),
        l(tcp.TCPLayer, debug=False),
    ])
    udp_layer = stateless_layers[2]
    tcp_layer = stateless_layers[-1]

    def stateful_layers(prev_layer, *args, **kwargs):
        try:
            layers = connect(
                prev_layer, [
                l(base.LineBufferLayer),
                #l(base.CloudToButtLayer, *args, **kwargs), 
                l(http.HTTPLayer, *args, **kwargs),
            ])
        except:
            prev_layer.next_layer = stateful_layers 
            raise
        # Fix prev_layer.next_layer munging
        prev_layer.next_layer = stateful_layers 
        print prev_layer.next_layer, 'state'
        return layers[0]

    tcp_layer.next_layer = stateful_layers
    udp_layer.register_app(udp.UDPVideoLayer)

    try:
        loop.start()
    except:
        tap.passthru()

