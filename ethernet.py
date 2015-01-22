# Packet sniffer in python
# For Linux

ETH_P_ALL = 3 

import socket
import select
import queue
import subprocess
import driver

class Ethernet(object):
    alice_nic="enp0s20u3u2"
    bob_nic="enp0s20u3u3"

    SNAPLEN=65536

    def __init__(self, alice_fn, bob_fn, tap=True, debug=False):
        self.alice_fn = alice_fn
        self.bob_fn = bob_fn
        self.debug = debug

        self.a_w = queue.Queue()
        self.b_w = queue.Queue()

        if tap:
            self.tap=driver.Tap()
        else:
            self.tap=None

    def alice_write(self, data):
        self.a_w.put(data)

    def bob_write(self, data):
        self.b_w.put(data)

    def run(self):
        def attach(nic):
            result = subprocess.call(["ifconfig",nic,"up","promisc"])
            if result:
                raise Exception("ifconfig {0} return exit code {1}".format(nic,result))
            sock = socket.socket(socket.AF_PACKET,socket.SOCK_RAW,socket.htons(ETH_P_ALL))
            sock.bind((nic,0))
            sock.setblocking(0)
            return sock

        alice_sock = attach(self.alice_nic)
        bob_sock = attach(self.bob_nic)

        if self.tap:
            self.tap.mitm()

        try:
            while True:
                to_w=[]
                if not self.a_w.empty():
                    to_w.append(alice_sock)
                if not self.b_w.empty():
                    to_w.append(bob_sock)

                r,w,e=select.select([alice_sock,bob_sock],to_w,[alice_sock,bob_sock])

                if alice_sock in r:
                    a=alice_sock.recv(self.SNAPLEN)
                    if self.debug:
                        print("ALICE:",' '.join([hex(c) for c in a]))
                    self.alice_fn(a, self.alice_write, self.bob_write)
                if bob_sock in r:
                    b=bob_sock.recv(self.SNAPLEN)
                    if self.debug:
                        print("BOB:",' '.join([hex(c) for c in b]))
                    self.bob_fn(b, self.bob_write, self.alice_write)
                if alice_sock in w:
                    while True:
                        try:
                            wd = self.a_w.get_nowait()
                            self.a_w.task_done()
                        except queue.Empty:
                            break
                        l=alice_sock.send(wd)
                if bob_sock in w:
                    while True:
                        try:
                            wd = self.b_w.get_nowait()
                            self.b_w.task_done()
                        except queue.Empty:
                            break
                        l=bob_sock.send(wd)
                if alice_sock in e:
                    raise "ALICE EXCEPTION"
                if alice_sock in e:
                    raise "BOB EXCEPTION"
        finally:
            if self.tap:
                self.tap.passthru()
