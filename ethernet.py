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
    @gen.coroutine
    def on_read(src, data):
        yield

    @gen.coroutine
    def write(dst, data):
        yield


def attach(nic):
    result = subprocess.call(["ifconfig",nic,"up","promisc"])
    if result:
        raise Exception("ifconfig {0} return exit code {1}".format(nic,result))
    sock = socket.socket(socket.AF_PACKET,socket.SOCK_RAW,socket.htons(ETH_P_ALL))
    sock.bind((nic,0))
    sock.setblocking(0)
    return sock

def eth_callback(from_sock, from_write, to_write, from_fn, fd, events):
    SNAPLEN=1550
    while True:
        try:
            data = from_sock.recv(SNAPLEN)
        except socket.error as e:
            if e.args[0] not in (errno.EWOULDBLOCK, errno.EAGAIN):
                raise
            return
        from_fn(data, from_write, to_write)

def build_ethernet_loop(alice_fn, bob_fn, debug=False):
    alice_nic="enp0s20u3u2"
    bob_nic="enp0s20u3u3"

    alice_sock = attach(alice_nic)
    bob_sock = attach(bob_nic)

    def write_fn(sock):
        def _fn(data):
            return sock.send(data)
        return _fn

    io_loop = tornado.ioloop.IOLoop.instance()

    alice_cb = functools.partial(eth_callback, alice_sock, write_fn(alice_sock), write_fn(bob_sock), alice_fn)
    bob_cb = functools.partial(eth_callback, bob_sock, write_fn(bob_sock), write_fn(alice_sock), bob_fn)

    io_loop.add_handler(alice_sock.fileno(), alice_cb, io_loop.READ)
    io_loop.add_handler(bob_sock.fileno(), bob_cb, io_loop.READ)

    return io_loop

