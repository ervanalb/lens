#!/usr/bin/python2
import dpkt
import driver
import enum
import ethernet 
import tcp

import tornado.gen as gen

class IPv4Layer(ethernet.NetLayer):
    @staticmethod
    def pretty_ip(ip):
        return ".".join([str(ord(x)) for x in ip])

    def __init__(self, prev_layer=None, next_layer=None, addr_filter=None):
        self.prev_layer = prev_layer
        self.next_layer = next_layer
        self.addr_filter = addr_filter

    @gen.coroutine
    def on_read(self, src, data):
        pkt = dpkt.ethernet.Ethernet(data)
        if pkt.type == dpkt.ethernet.ETH_TYPE_IP:
            if self.addr_filter is None or self.pretty_ip(pkt.data.src) in self.addr_filter or self.pretty_ip(pkt.data.dst) in self.addr_filter:
                #print src, repr(pkt)
                yield self.bubble(src, data)
            return 
        yield self.write(self.route(src), data)

class TCPPassthruLayer(ethernet.NetLayer):
    def __init__(self, prev_layer=None, next_layer=None, ports=None):
        self.prev_layer = prev_layer
        self.next_layer = next_layer
        self.ports = ports

    @gen.coroutine
    def on_read(self, src, data):
        pkt = dpkt.ethernet.Ethernet(data)
        if pkt.type == dpkt.ethernet.ETH_TYPE_IP:
            if pkt.data.p == dpkt.ip.IP_PROTO_TCP:
                if pkt.data.data.sport in self.ports or pkt.data.data.dport in self.ports:
                    yield self.write(self.route(src), data)
                    return
        yield self.bubble(src, data)

class CloudToButtLayer(ethernet.NetLayer):
    def __init__(self, prev_layer=None, next_layer=None):
        self.prev_layer = prev_layer
        self.next_layer = next_layer

    @gen.coroutine
    def on_read(self, src, data, *args, **kwargs):
        butt_data = data.replace("cloud", "butt")
        yield self.bubble(src, butt_data, *args, **kwargs)

def connect(layer_list):
    for a, b in zip(layer_list, layer_list[1:]):
        a.next_layer = b
        b.prev_layer = a

if __name__ == "__main__":
    addr = "18.238.0.97"
    print "Capturing traffic to:", addr

    tap = driver.Tap()

    loop, link_layer = ethernet.build_ethernet_loop()
    tap.mitm()

    connect([
        link_layer,
        IPv4Layer(addr_filter=[addr]),
        TCPPassthruLayer(ports=[22]),
        tcp.TCPLayer(),
        CloudToButtLayer()
    ])

    try:
        loop.start()
    except:
        tap.passthru()

