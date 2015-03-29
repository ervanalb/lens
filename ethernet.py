# Packet sniffer in python
# For Linux

ETH_P_ALL = 3 

import dpkt
import driver
import errno
import functools
import select
import socket
import subprocess

import tornado.ioloop
import tornado.iostream
import tornado.gen as gen

try:
    import queue
except:
    import Queue as queue

class NetLayer(object):
    routing = {
        1: 0,
        0: 1
    }
    IN_TYPES = set()
    OUT_TYPE = None

    def __init__(self, prev_layer=None, next_layer=None, debug=True):
        self.prev_layer = prev_layer
        self.next_layer = next_layer
        self.debug = debug

    @gen.coroutine
    def on_read(self, src, payload, header=None):
        yield self.bubble(*args **kwargs)

    @gen.coroutine
    def bubble(self, src, *args, **kwargs):
        if self.next_layer is not None:
            yield self.next_layer.on_read(src, *args, **kwargs)
        #elif self.prev_layer is not None:
            #yield self.prev_layer.write(self.route(src), *args, **kwargs)
        else:
            yield self.write(self.route(src), *args, **kwargs)

    @gen.coroutine
    def passthru(self, src, *args, **kwargs):
        yield self.prev_layer.write(self.route(src), *args, **kwargs)

    @gen.coroutine
    def write(self, dst, payload, header=None):
        # Override me
        yield self.prev_layer.write(dst, payload, header)

    def route(self, key):
        return self.routing[key]

    def unroute(self, key):
        #TODO
        return self.routing[key]

class LinkLayer(object):
    SNAPLEN=1550
    IN_TYPES = set()
    OUT_TYPE = "Raw"
    def __init__(self, streams, next_layer=None):
        self.next_layer = next_layer
        self.streams = streams

    @gen.coroutine
    def on_read(self, src):
        while True:
            try:
                #FIXME
                data = self.streams[src].socket.recv(self.SNAPLEN)
            except socket.error as e:
                if e.args[0] not in (errno.EWOULDBLOCK, errno.EAGAIN):
                    raise
                return
            if self.next_layer:
                yield self.next_layer.on_read(src, data[:-2])

    @gen.coroutine
    def write(self, dst, data):
        yield self.streams[dst].write(data)


class EthernetLayer(NetLayer):
    IN_TYPES = {"Raw"}
    OUT_TYPE = "Ethernet"

    @staticmethod
    def pretty_mac(mac):
        return ":".join(["{:02x}".format(ord(x)) for x in mac])
    @staticmethod
    def wire_mac(mac):
        return "".join([chr(int(x, 16)) for x in mac.split(":")])

    @gen.coroutine
    def on_read(self, src, data):
        try:
            pkt = dpkt.ethernet.Ethernet(data)
        except dpkt.NeedData:
            yield self.passthru(src, data)
            return
        if self.debug:
            print "eth recv", src, repr(pkt), "\n"
        header = {
            "eth_dst": self.pretty_mac(pkt.dst),
            "eth_src": self.pretty_mac(pkt.src),
            "eth_type": pkt.type,
        }
        yield self.bubble(src, pkt.data, header)

    @gen.coroutine
    def write(self, dst, payload, header):
        pkt = dpkt.ethernet.Ethernet(
                dst=self.wire_mac(header["eth_dst"]),
                src=self.wire_mac(header["eth_src"]),
                type=header["eth_type"],
                data=payload)
        if self.debug:
            str(pkt)
            print "eth send", dst, repr(pkt), "\n"

        yield self.prev_layer.write(dst, str(pkt))

def attach(nic):
    result = subprocess.call(["ifconfig",nic,"up","promisc"])
    if result:
        raise Exception("ifconfig {0} return exit code {1}".format(nic,result))
    sock = socket.socket(socket.AF_PACKET,socket.SOCK_RAW,socket.htons(ETH_P_ALL))
    sock.bind((nic,0))
    sock.setblocking(0)
    return sock


def eth_callback(layer, src, fd, events):
    #while True:
    for i in range(events):
        try:
            layer.on_read(src)
        except socket.error as e:
            if e.args[0] not in (errno.EWOULDBLOCK, errno.EAGAIN):
                raise
            return

def build_ethernet_loop():
    alice_nic="enp0s20u3u1"
    bob_nic="enp0s20u3u2"

    alice_sock = attach(alice_nic)
    bob_sock = attach(bob_nic)

    def write_fn(sock):
        def _fn(data):
            return sock.send(data)
        return _fn

    io_loop = tornado.ioloop.IOLoop.instance()

    alice_stream = tornado.iostream.IOStream(alice_sock)
    bob_stream = tornado.iostream.IOStream(bob_sock)

    link_layer = LinkLayer([alice_stream, bob_stream])

    alice_cb = functools.partial(eth_callback, link_layer, 0)
    bob_cb = functools.partial(eth_callback, link_layer, 1)

    io_loop.add_handler(alice_sock.fileno(), alice_cb, io_loop.READ)
    io_loop.add_handler(bob_sock.fileno(), bob_cb, io_loop.READ)

    return io_loop, link_layer

