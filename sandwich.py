#!/usr/bin/python2
import ethernet 
import driver
import scapy.all as sc
from decorators import *
from collections import namedtuple
import enum
from buffer import FifoBuffer

FIN = 0x01
SYN = 0x02
RST = 0x04
PSH = 0x08
ACK = 0x10
URG = 0x20
ECE = 0x40
CWR = 0x80

@enum.unique
class TCPState(enum.Enum):
    WAITING = 1
    SEEN_SYN = 2
    SPLIT = 3


def connection_id(pkt):
    # Generate a tuple representing the stream 
    # (source host addr, source port, dest addr, dest port)
    if "IP" in pkt:
        ip_layer = "IP"
    elif "IPv6" in pkt:
        ip_layer = "IPv6"
    else:
        print repr(pkt)
        raise Exception("No IP layer in packet!")
    return ((pkt[ip_layer].src, pkt["TCP"].sport),
            (pkt[ip_layer].dst, pkt["TCP"].dport))

def has_payload(pkt):
    payload = pkt["TCP"].payload
    if isinstance(payload, sc.Padding):
        return False
    return bool(payload)

def conn_pkt(conn, from_recv, flags=""):
    prefix = "recv_" if from_recv else "send_"
    prefix_r = "recv_" if not from_recv else "send_"
    get = lambda x: conn[prefix + x]
    getr = lambda x: conn[prefix_r + x]
    pkt = get("pkt")
    pkt["IP"].id += 1

    payload = ""
    seq = getr('seq')
    tosend = getr('tosend')
    if tosend and "F" not in flags:
        if getr('unacked'):
            print "waiting on ack on", getr('unacked')
            seq, payload = getr('unacked')[0]
            flags += "P"
        else:
            payload = tosend[:1400]
            conn[prefix_r + "tosend"] = tosend[1400:]
            flags += "P"
            getr('unacked').append((seq, payload))

    pkt_tcp = sc.TCP(sport=get("port"), dport=getr("port"),
                     seq=seq, ack=getr("ack"),
                     window=8192,
                     #options   = [('Timestamp', (0, 0)), ('EOL', None)],
                     flags=flags
                     )
    p =  pkt / pkt_tcp / payload
    p.show2()
    #print "SENDING PACKET", flags, (getr('seq'), getr('ack')), from_recv, p["IP"].chksum, repr(p)
    return p

# Example Sequence Diagram
# Data between the D channels can be modified arbitrarily
# The two halves of D represented here form the "bread" of the "TCP sandwich" 

# A             D               B
# |           |   |             |
# |---SYN-----|---|------------>|     ; SYN gets passed through             (Step 1)
# |           |  /|<--SYNACK----|     ; SYNACK is intercepted by D...       (Step 2)
# |           | / |---ACK------>|     ; ...and responded to immediately     (Step 2)
# |<--SYNACK--|/  |             |     ; ...and then copied out to A         (Step 2)
# |---ACK---->|   |             |     ; ...and then A responds, but the ACK is not responded to
# |           |   |             |     ; 
# |---P------>|\  |             |     ; Data pushed to D is queued up to send
# |<--ACK-----| \ |             |     ; ...and acked immediately
# |           |  \|---P-------->|     ; Packets are forged to push data to B
# |           |  /|<--P-ACK-----|     ; ACKs can potentially also contain data 
# |           | / |---ACK------>|     ; 
# |<--P-------|/  |             |     ; 
# |---ACK---->|   |             |     ; 
# |           |   |             |     ; 


connections = {}


def make_sandwich(side, ip_addr):
    @ipv4_prudish_mode(addr=ip_addr, drop=False)
    @tcp_ignore_port(22)
    def _sandwich(sent_data, write_back, write_fwd):
        p = sc.Ether(sent_data)
        #print repr(p)
        if "TCP" in p:
            p_ip = p["IP"]
            p_tcp = p["TCP"]
            conn_id = connection_id(p)
            is_receiver = False

            if conn_id[::-1] in connections: # is_receiver 
                is_receiver = True
                conn_id = conn_id[::-1]
            conn = connections.get(conn_id, {"state": TCPState.WAITING})

            prefix = "recv_" if is_receiver else "send_"
            prefix_r = "recv_" if not is_receiver else "send_"

            print side, p_tcp.sprintf("tcp: sport %TCP.sport% \t dport %TCP.dport% \t flags %TCP.flags%"), conn["state"] != TCPState.WAITING, is_receiver 
            p_fwd = None
            p_back = None

            # send_ack

            # FIXME: the packet could have a payload *and* be SYN

            if has_payload(p_tcp) and not p_tcp.flags & SYN:
                if conn["state"] == TCPState.SPLIT:
                    print "DATA ---------", len(p_tcp.load), conn
                    print repr(p_tcp)
                    if is_receiver:
                        if conn["recv_ack"] == p_tcp.seq: # No effort to reconstruct out-of-order packets yet
                            size = len(p_tcp.load)
                            conn["recv_load"] += p_tcp.load
                            conn["send_tosend"] += p_tcp.load.replace('cloud', 'butt')
                            conn["recv_ack"] += size
                            #conn["recv_seq"] = p_tcp.seq
                            # Respond to new data with ACK
                            p_ack = conn_pkt(conn, from_recv=False, flags="A")
                            write_back(str(p_ack))

                            p_fwd = conn_pkt(conn, from_recv=True, flags="A")
                            write_fwd(str(p_fwd))
                        else:
                            print "NOT ACKING PACKET, out of order, R", conn, repr(p_tcp)
                    else:
                        if conn["send_ack"] == p_tcp.seq: # No effort to reconstruct out-of-order packets yet
                            size = len(p_tcp.load)
                            conn["send_load"] += p_tcp.load
                            conn["recv_tosend"] += p_tcp.load.replace('butt', 'cloud')
                            conn["send_ack"] += size
                            #conn["send_seq"] = p_tcp.seq
                            # Respond to new data with ACK
                            p_ack = conn_pkt(conn, from_recv=True, flags="A")
                            write_back(str(p_ack))

                            p_fwd = conn_pkt(conn, from_recv=False, flags="A")
                            write_fwd(str(p_fwd))
                        else:
                            print "NOT ACKING PACKET, out of order, S", conn, repr(p_tcp)
                else:
                    # We didn't capture the beginning, so don't muck with it
                    write_fwd(sent_data)

            if p_tcp.flags & SYN:
                print side, "SYN", conn_id, conn, p_tcp.seq, p_tcp.ack
                ex_pkt = p.copy()
                ex_pkt["IP"].remove_payload()
                print "ORIG CHECKSUM:", ex_pkt["IP"].chksum
                del ex_pkt["IP"].chksum
                del ex_pkt["IP"].len
                if p_tcp.flags & ACK: # SYNACK, Reciever
                    # Step 2: Recieve a SYNACK
                    #         Respond back with ACK, assuming the connection will succeed 
                    #         Send forward a SYNACK 
                    if not is_receiver:
                        raise Exception("Weird sequencing")
                    if p_tcp.ack != conn["send_ack"]:
                        print "INVALID SYNACK", p_tcp.ack, conn["send_ack"]
                    else:
                        print "VALID SYNACK"
                    conn["send_seq"] = p_tcp.seq + 1
                    conn["send_ack"] = p_tcp.ack
                    conn["recv_seq"] = p_tcp.ack
                    conn["recv_ack"] = p_tcp.seq + 1
                    conn["recv_load"] = ""
                    conn["recv_tosend"] = ""
                    conn["recv_unacked"] = []
                    conn["recv_pkt"] = ex_pkt
                    conn["state"] = TCPState.SPLIT

                    # Generate the ACK to respond back with
                    # conn_pkt populates ports, seq, ack, and unimportant options
                    # flags and payload are the only things that need to be set
                    p_resp = conn_pkt(conn, from_recv=False, flags="A")
                    write_back(str(p_resp))

                    # Forward the SYNACK
                    p_sa = conn_pkt(conn, from_recv=True, flags="SA")
                    write_fwd(str(p))
                else: # Sender
                    # Step 1: SYN Packet to start connection
                    # Pass the SYN packet through unmodified but save its format to spoof later
                    # We cannot ack this packet because we have no idea if the host will respond
                    if is_receiver:
                        raise Exception("Weird sequencing")
                    conn["send_port"] = p_tcp.sport 
                    conn["recv_port"] = p_tcp.dport
                    conn["recv_seq"] = p_tcp.seq 
                    conn["send_ack"] = p_tcp.seq + 1
                    conn["send_load"] = ""
                    conn["send_tosend"] = ""
                    conn["send_unacked"] = []
                    conn["send_pkt"] = ex_pkt
                    conn["state"] = TCPState.SEEN_SYN
                    # Respond with the exact packet that was recieved
                    write_fwd(str(p))

            elif p_tcp.flags & ACK: 
                if conn["state"] == TCPState.SPLIT:
                    # Maybe there should also be some checks or something?
                    #print 'ack, isR:', is_receiver, p_tcp.ack, conn
                    #FIXME: only works for window size of 1
                    if is_receiver: 
                        print 'unacked', p_tcp.ack, conn['recv_unacked']
                        conn["recv_unacked"] = filter(lambda (s, p): s >= p_tcp.ack, conn["recv_unacked"])
                        conn["recv_seq"] = p_tcp.ack
                    else:
                        print 'unacked', p_tcp.ack, conn['send_unacked']
                        conn["send_unacked"] = filter(lambda (s, p): s >= p_tcp.ack, conn["send_unacked"])
                        conn["send_seq"] = p_tcp.ack
                    print "ACK", repr(p_tcp)
                else:
                    print "unsplit ACK"


            if p_tcp.flags & RST:
                print "RST"
                conn = None
                write_fwd(str(p))

            if p_tcp.flags & FIN:
                print "FIN"
                #conn = None
                #conn[prefix_r + "seq"] += 1
                #conn[prefix + "ack"] += 1
                p_fin = conn_pkt(conn, from_recv=is_receiver, flags=p_tcp.flags)
                write_fwd(str(p))

            if conn:
                connections[conn_id] = conn
            else:
                print "CLOSING:", conn
                if conn_id in connections:
                    del connections[conn_id]
                else:
                    print "(not active conn)"
        else:
            write_fwd(sent_data)
    return _sandwich

if __name__ == "__main__":
    addr = "18.238.0.97"
    print "Capturing traffic to:", addr

    eth = ethernet.Ethernet(make_sandwich("A", addr), make_sandwich("B", addr))
    eth.run()
