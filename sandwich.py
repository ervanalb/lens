import ethernet 
import driver
import scapy.all as sc
from decorators import *
from collections import namedtuple
import enum

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

def conn_pkt(conn, from_recv):
    prefix = "recv_" if from_recv else "send_"
    prefix_r = "recv_" if not from_recv else "send_"
    get = lambda x: conn[prefix + x]
    getr = lambda x: conn[prefix_r + x]
    pkt = get("pkt")
    pkt["IP"].id += 1
    pkt_tcp = TCP(sport=get("port"), dport=getr("port"),
                  seq=get("seq"), ack=get("ack"),
                  window=8192,
                  options   = [('Timestamp', (0, 0)), ('EOL', None)]
                  )
    return pkt / pkt_tcp




connections = {}

def make_sandwich(side):
    @ipv4_prudish_mode(addr="18.238.7.128")
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

            print side, p_tcp.sprintf("%TCP.sport% \t %TCP.dport% \t %TCP.flags%"), conn["state"] != TCPState.WAITING, is_receiver 

                # send_ack

            if has_payload(p_tcp) and not p_tcp.flags & SYN:
                if conn["state"] == TCPState.SPLIT:
                    if is_receiver:
                        size = p_tcp.seq - conn["recv_seq"] 
                        print "recv size", size, len(p_tcp.load)
                        if size == len(p_tcp.load):
                            conn["recv_load"] += p_tcp.load
                            p_resp = conn_pkt(con, from_recv=True)
                    else:
                        conn["send_load"] += p_tcp.load
                else:
                    p_resp = p
                
            if p_tcp.flags & SYN:
                print side, "SYN", conn_id, conn
                ex_pkt = p.copy()
                ex_pkt["IP"].remove_payload()
                del ex_pkt["IP"].chksum
                if p_tcp.flags & ACK: # SYNACK, Reciever
                    if not is_receiver:
                        raise Exception("Weird sequencing")
                    conn["recv_seq"] = p_tcp.seq
                    conn["recv_ack"] = p_t
                    conn["recv_payload"] = ""
                    conn["recv_pkt"] = ex_pkt
                    p_resp = conn_pkt(conn, from_recv=False)
                    p_resp["TCP"].flags = "A"
                else: # Sender
                    if is_receiver:
                        raise Exception("Weird sequencing")
                    conn["send_port"] = p_tcp.sport
                    conn["recv_port"] = p_tcp.dport
                    conn["send_seq"] = p_tcp.seq
                    conn["send_ack"] = 1
                    conn["send_payload"] = ""
                    conn["send_pkt"] = ex_pkt
                    # Pass on SYN
                    p_resp = p
                    #write_fwd(sent_data)

            elif p_tcp.flags & ACK:
                if conn["state"] == TCPState.SYN_RECEIVED:
                    conn["state"] = TCPState.ESTABLISHED
                elif conn["state"] == TCPState.LAST_ACK:
                    # close
                    conn = None


            if p_tcp.flags & RST:
                print "RST"
                conn = None

            if p_tcp.flags & FIN:
                print "FIN"
                conn = None

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
    eth = ethernet.Ethernet(make_sandwich("A"), make_sandwich("B"))
    eth.run()
