# For Linux

import socket
import subprocess

import tornado.ioloop
import tornado.iostream

from base import NetLayer

class LinkLayer(NetLayer):
    SNAPLEN=1550
    ETH_P_ALL = 3 

    ALICE = 0
    BOB = 1

    def __init__(self, alice_nic = "tapa", bob_nic = "tapb", *args, **kwargs):
        super(LinkLayer, self).__init__(*args, **kwargs)
        alice_sock = self.attach(alice_nic)
        bob_sock = self.attach(bob_nic)

        io_loop = tornado.ioloop.IOLoop.instance()

        self.alice_stream = tornado.iostream.IOStream(alice_sock)
        self.bob_stream = tornado.iostream.IOStream(bob_sock)

        io_loop.add_handler(alice_sock.fileno(), self.alice_read, io_loop.READ)
        io_loop.add_handler(bob_sock.fileno(), self.bob_read, io_loop.READ)

    # This layer is a SOURCE
    # so it will never consume packets
    def match(self, src, header):
        return False

    @classmethod
    def attach(cls, nic):
        result = subprocess.call(["ip","link","set","up","promisc","on","dev",nic])
        if result:
            raise Exception("ip link dev {0} returned exit code {1}".format(nic,result))
        sock = socket.socket(socket.AF_PACKET,socket.SOCK_RAW,socket.htons(cls.ETH_P_ALL))
        sock.bind((nic,0))
        sock.setblocking(0)
        return sock

    # coroutine
    def alice_read(self, fd, event):
        data = self.alice_stream.socket.recv(self.SNAPLEN)
        return self.on_read(self.ALICE, {}, data[:-2])

    # coroutine
    def bob_read(self, fd, event):
        data = self.bob_stream.socket.recv(self.SNAPLEN)
        return self.on_read(self.BOB, {}, data[:-2])

    # coroutine
    def write(self, dst, header, data):
        if dst == self.ALICE:
            return self.alice_stream.write(data)
        elif dst == self.BOB:
            return self.bob_stream.write(data)
        else:
            raise Exception("Bad destination")
