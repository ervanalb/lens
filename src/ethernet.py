# For Linux

ETH_P_ALL = 3 

import dpkt
import driver
import errno
import functools
import select
import socket
import subprocess
import sys

import tornado.ioloop
import tornado.iostream
import tornado.gen as gen

try:
    import queue
except:
    import Queue as queue

from base import NetLayer

class LinkLayer(object):
    # Not actually a subclass of NetLayer, but exposes a similar interface for consistency
    SNAPLEN=1550

    IN_TYPES = set()
    OUT_TYPE = "Raw"
    SINGLE_CHILD = True

    def __init__(self, streams):
        self.streams = streams
        self.child = None

    def register_child(self, child):
        self.child = child
        child.parent = self

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
            if self.child is not None:
                yield self.child.on_read(src, {}, data[:-2])
            else:
                dst = 1 - src # XXX
                yield self.write(dst, {}, data[:-2])

    @gen.coroutine
    def write(self, dst, header, data):
        try:
            yield self.streams[dst].write(data)
        except tornado.iostream.StreamClosedError:
            print "Link Layer stream closed; exiting..."
            sys.exit(-1)


class EthernetLayer(NetLayer):
    IN_TYPES = {"Raw"}
    OUT_TYPE = "Ethernet"
    SINGLE_CHILD = False

    def __init__(self, *args, **kwargs):
        super(EthernetLayer, self).__init__(*args, **kwargs)
        self.seen_macs = {k: set() for k in self.routing.keys()}

    @staticmethod
    def pretty_mac(mac):
        return ":".join(["{:02x}".format(ord(x)) for x in mac])
    @staticmethod
    def wire_mac(mac):
        return "".join([chr(int(x, 16)) for x in mac.split(":")])

    def match_child(self, src, header, key):
        return key == header["eth_type"]

    @gen.coroutine
    def on_read(self, src, header, data):
        try:
            pkt = dpkt.ethernet.Ethernet(data)
        except dpkt.NeedData:
            yield self.passthru(src, header, data)
            return
        header = {
            "eth_dst": self.pretty_mac(pkt.dst),
            "eth_src": self.pretty_mac(pkt.src),
            "eth_type": pkt.type,
        }
        self.seen_macs[src].add(header["eth_src"])
        yield self.bubble(src, header, pkt.data)

    @gen.coroutine
    def write(self, dst, header, payload):
        pkt = dpkt.ethernet.Ethernet(
                dst=self.wire_mac(header["eth_dst"]),
                src=self.wire_mac(header["eth_src"]),
                type=header["eth_type"],
                data=payload)
        yield self.write_back(dst, header, str(pkt))

    def do_help(self):
        return """Ethernet Layer:
        help - print this message
        list - list MAC addresses seen"""

    def do_list(self):
        output = ""
        for src, macs in self.seen_macs.items():
            output += "Source %d:\n" % src
            for mac in macs:
                output += " - %s\n" % mac
        return output

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

def build_ethernet_loop(alice_nic="enp0s20u1", bob_nic="enp0s20u2"):
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

