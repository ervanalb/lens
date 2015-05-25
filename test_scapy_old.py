import subprocess
import socket
import scapy.all as sc

ETH_P_ALL = 3 
alice_nic="enp0s20u3u2"
bob_nic="enp0s20u3u3"

def attach(nic):
    result = subprocess.call(["ifconfig",nic,"up","promisc"])
    if result:
        raise Exception("ifconfig {0} return exit code {1}".format(nic,result))
    sock = socket.socket(socket.AF_PACKET,socket.SOCK_RAW,socket.htons(ETH_P_ALL))
    sock.bind((nic,0))
    #sock.setblocking(0)
    return sock

an = attach(alice_nic)
bn = attach(bob_nic)

eth = sc.Ether()
eth.payload = 'x' * 128
x = bytearray(str(eth))
#x = bytearray("X" * 1514, "utf-8")
print "sending", len(x)

print("write", an.send(x))
d = bn.recv(1600)
print(len(d))
de = sc.Ether(d)
print(sc.hexdump(de))
print(de.show())
print(repr(str(de)))

