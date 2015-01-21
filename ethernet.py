# Packet sniffer in python
# For Linux

ETH_P_ALL = 3 

import socket
import select

class Ethernet(object):
    alice_nic="enp0s20u3u2"
    bob_nic="enp0s20u3u3"

    SNAPLEN=65536

    @staticmethod
    def attach(nic):
        sock = socket.socket(socket.AF_PACKET,socket.SOCK_RAW,socket.htons(ETH_P_ALL))
        sock.bind((nic,0))
        sock.setblocking(0)
        return sock

    def __init__(self, alice_fn, bob_fn, debug=True):
        self.alice_fn = alice_fn
        self.bob_fn = bob_fn
        self.debug = debug

        self.a_w = bytearray()
        self.b_w = bytearray()

    def alice_write(self, data):
        self.a_w += data

    def bob_write(self, data):
        self.b_w += data

    def run(self):
        alice_sock=attach(self.alice_nic)
        bob_sock=attach(self.bob_nic)

        while True:
            to_w=[]
            if len(a_w) > 0:
                to_w.append(alice_sock)
            if len(b_w) > 0:
                to_w.append(bob_sock)

            r,w,e=select.select([alice_sock,bob_sock],to_w,[alice_sock,bob_sock])

            if alice_sock in r:
                a=alice_sock.recv(self.SNAPLEN)
                if self.debug:
                    print("ALICE:",' '.join([hex(c) for c in a]))
                #b_w += a
                self.alice_fn(b, self.alice_write, self.bob_write)
            if bob_sock in r:
                b=bob_sock.recv(self.SNAPLEN)
                if self.debug:
                    print("BOB:",' '.join([hex(c) for c in b]))
                #a_w += b
                self.bob_fn(b, self.bob_write, self.alice_write)
            if alice_sock in w:
                l=alice_sock.send(a_w)
                a_w=a_w[l:]
            if bob_sock in w:
                l=bob_sock.send(b_w)
                b_w=b_w[l:]
            if alice_sock in e:
                raise "ALICE EXCEPTION"
            if alice_sock in e:
                raise "BOB EXCEPTION"

# receive a packet
#while True:
#    try:
#        a=alice_sock.recv(65536)
#        print("ALICE:",' '.join([hex(c) for c in a]))
#        print(bob_sock.send(a))
#    except socket.error as e:
#        if e.errno != 11:
#            raise
#    try:
#        b=bob_sock.recv(65536)
#        print("BOB:",' '.join([hex(c) for c in b]))
#        print(alice_sock.send(b))
#    except socket.error as e:
#        if e.errno != 11:
#            raise
