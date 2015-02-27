# Packet sniffer in python
# For Linux

ETH_P_ALL = 3 

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
    @gen.coroutine
    def on_read(self, src, data):
        yield

    @gen.coroutine
    def bubble(self, src, data, *args, **kwargs):
        if self.next_layer is not None:
            yield self.next_layer.on_read(src, data, *args, **kwargs)
        elif self.prev_layer is not None:
            yield self.prev_layer.write(self.route(src), data, *args, **kwargs)
        else:
            yield self.write(self.route(src), data, *args, **kwargs)

    @gen.coroutine
    def passthru(self, src, data):
        if self.prev_layer is not None:
            yield self.prev_layer.write(self.route(src), data)

    @gen.coroutine
    def write(self, dst, data):
        if self.prev_layer is not None:
            yield self.prev_layer.write(dst, data)

    def route(self, key):
        return self.routing[key]

    def unroute(self, key):
        #TODO
        return self.routing[key]

class LinkLayer(object):
    SNAPLEN=1550
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
    alice_nic="enp0s20u3u2"
    bob_nic="enp0s20u3u3"

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

