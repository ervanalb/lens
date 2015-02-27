from ethernet import NetLayer

from tornado import gen

import collections
import datetime
import dpkt 
import struct
import time

TCP_FLAGS = {
    "A": dpkt.tcp.TH_ACK,
    "C": dpkt.tcp.TH_CWR,
    "E": dpkt.tcp.TH_ECE,
    "F": dpkt.tcp.TH_FIN,
    "P": dpkt.tcp.TH_PUSH,
    "R": dpkt.tcp.TH_RST,
    "S": dpkt.tcp.TH_SYN,
    "U": dpkt.tcp.TH_URG
}

def tcp_dump_flags(flagstr):
    out = 0
    for f in flagstr:
        out |= TCP_FLAGS[f]
    return out

def tcp_read_flags(flagbyte):
    out = ""
    for (s, f) in TCP_FLAGS.items():
        if flagbyte & f:
            out += s
    return out

def tcp_dump_opts(optlist):
    buf = ''
    for o, d in optlist:
        buf += chr(o)
        if o != dpkt.tcp.TCP_OPT_NOP:
            l = len(d) + 2
            buf += chr(l) + d
    padding = chr(dpkt.tcp.TCP_OPT_NOP) * ((4 - (len(buf) % 4)) % 4)
    return padding + buf

def tcp_has_payload(tcp_pkt):
    return bool(tcp_pkt.data)

# Connection
def connection_id(pkt):
    # Generate a tuple representing the stream 
    # (source host addr, source port, dest addr, dest port)
    return ((pkt.data.src, pkt.data.data.sport),
            (pkt.data.dst, pkt.data.data.dport))

class TimestampEstimator(object):
    def __init__(self):
        self.samples = []
        self.offset = None
        self.rate = None

    def recalculate_lsq(self):
        if len(self.samples) < 1:
            return 
        if len(self.samples) == 1:
            l, s = self.samples[0]
            self.rate = 1
            self.offset = l * -self.rate + s
            return

        lta = sum(zip(*self.samples)[0]) / float(len(self.samples))
        sta = sum(zip(*self.samples)[1]) / float(len(self.samples))

        self.rate = sum([(l - lta) * (s - sta) for (l, s) in self.samples]) / sum([(l - lta) ** 2 for (l, s) in self.samples])
        self.offset = sta - self.rate * lta

    def recalculate_median(self):
        if len(self.samples) < 2:
            return
        deltas = [(s2 - s1) / (l2 - l1 + 0.1) for (l1, s1), (l2, s2) in zip(self.samples, self.samples[1:])]
        deltas.sort()
        self.rate = deltas[len(deltas) / 2]
        # Skew down
        self.rate *= 0.50

    def put_sample(self, sample, local_time=None):
        if sample < 1:
            return
        if local_time is None:
            local_time = time.time()
        if len(self.samples):
            l, s = self.samples[0]
            if s > sample:
                # Resetting
                print "RESET"
                self.samples = []
        self.samples.append((local_time, sample))
        self.recalculate_median()

    def get_time(self, local_time=None):
        if len(self.samples) == 0:
            return 0
        elif len(self.samples) == 1:
            return self.samples[0][1]

        if self.rate is None:
            return 0
        if local_time is None:
            local_time = time.time()

        l, s = self.samples[-1]
        return int((local_time - l) * self.rate + s) & 0xFFFFFFFF
        #return int(local_time * self.rate + self.offset)


# Half Connection attributes
# From the perspective of sending packets back through the link
#
# eth_src / eth_dst - Ethernet source/dest MAC addrs
# ip_src / ip_dst - IP address of source / dest
# ip_ttl - IP TTL value
# sport / dport - TCP ports source / dest
# state - closed, opening, open, closing
# seq - seq number of sent data
# ack - ack number of sent data
# received data
# data to send

class TCPLayer(NetLayer):
    def __init__(self, next_layer=None, prev_layer=None):
        self.next_layer = next_layer
        self.prev_layer = prev_layer
        self.connections = {}
        self.timers = collections.defaultdict(TimestampEstimator)

    @gen.coroutine
    def on_read(self, src, data):
        pkt = dpkt.ethernet.Ethernet(data)

        if pkt.type != dpkt.ethernet.ETH_TYPE_IP or pkt.data.p != dpkt.ip.IP_PROTO_TCP:
            yield self.passthru(src, data)
            return 

        if self.prev_layer is None:
            yield self.passthru(src, data)
            return 

        #TODO: validate checksums / packet

        pkt_ip = pkt.data
        pkt_tcp = pkt.data.data
        tcp_opts = dpkt.tcp.parse_opts(pkt_tcp.opts)
        tcp_opts_dict = dict(tcp_opts)

        dst = self.route(src)
        conn_id = connection_id(pkt)
        if conn_id[::-1] in self.connections: # is_receiver
            # The connection was initiated by the dst
            conn_id = conn_id[::-1]
            sender, receiver = dst, src 
        else:
            sender, receiver = src, dst

        # For now, assume that connections are symmetric
        conn = self.connections.get(conn_id, {src: {}, dst: {}})

        src_conn = conn[src]
        dst_conn = conn[dst]
        sender_conn = conn[sender]
        receiver_conn = conn[receiver]
        commit = False

        host_ip = pkt_ip.src
        dest_ip = pkt_ip.dst

        passthru = True

        # Update timestamps
        if dpkt.tcp.TCP_OPT_TIMESTAMP in tcp_opts_dict:
            ts_val, ts_ecr = struct.unpack('II', tcp_opts_dict[dpkt.tcp.TCP_OPT_TIMESTAMP])
            dst_conn['ts_val'] = ts_val
            dst_conn['ts_ecr'] = ts_ecr
            t = self.timers[host_ip].get_time()
            #print src, ts_val, t, '%', (ts_val - t) / (ts_val + 0.1) * 100
            self.timers[host_ip].put_sample(ts_val)

        if tcp_has_payload(pkt_tcp):
            if src_conn.get("state") == "ESTABLISHED":
                data = pkt_tcp.data
                print "data", src, pkt_tcp["seq"], pkt_tcp["ack"], len(data), data[:8]
                src_conn["in_buffer"] += data
                src_conn["ack"] += len(data)

                yield self.write_packet(src, src_conn, flags="A")

                #mod_data = data.replace("html", "butts")
                #dst_conn["out_buffer"] += mod_data
                #yield self.write_packet(dst, dst_conn, flags="A")
                yield self.bubble(src, data, conn_id=conn_id)
                passthru = False

        if pkt_tcp.flags & dpkt.tcp.TH_SYN:
            # Assume we aren't redirecting the traffic, just modifying the contents
            commit = True

            dst_conn["eth_src"] = pkt.src
            dst_conn["eth_dst"] = pkt.dst
            dst_conn["ip_src"] = pkt_ip.src
            dst_conn["ip_dst"] = pkt_ip.dst
            dst_conn["ip_ttl"] = pkt_ip.ttl
            dst_conn["sport"] = pkt_tcp.sport
            dst_conn["dport"] = pkt_tcp.dport

            dst_conn["out_buffer"] = ""
            dst_conn["in_buffer"] = ""
            dst_conn["unacked"] = []

            #TODO
            dst_conn["seq"] = pkt_tcp.seq
            src_conn["ack"] = pkt_tcp.seq + 1
            #dst_conn["ack"] = pkt_tcp.ack

            print 'syn', tcp_read_flags(pkt_tcp.flags),dst_conn.get('state'), src_conn.get('state')


# A           | D_sender    | D_reciever  | B
# ------------------------------------------------------------
# SYN-SENT    |             | SYN-SENT    |             ; -> SYN ->
# SYN-SENT    | SYN-RECV    | ESTABLISHED | SYN-RECV    ; SYNACK <-
# ESTABLISHED | SYN-RECV    | ESTABLISHED | SYN-RECV    ; <- SYNACK
# ESTABLISHED | SYN-RECV    | ESTABLISHED | ESTABLISHED ; ACK ->
# ESTABLISHED | ESTABLISHED | ESTABLISHED | ESTABLISHED ; -> ACK

# A           | D_sender    | D_reciever  | B
# ------------------------------------------------------------
# Sa+1 , -    | -    , Sa+1 | Sa+1 , -    |             ; -> SYN -> (Sa,-)
# Sa+1 , -    | Sb   , Sa+1 | Sa+1 , Sb+1 | Sb+1 , Sa+1 ; SYNACK <- (Sb, Sa+1)
# Sa+1 , Sb+1 | Sb+1 , Sa+1 | Sa+1 , Sb+1 | Sb+1 , Sa+1 ; <- SYNACK (Sb, Sa+1)
# Sa+1 , Sb+1 | Sb+1 , Sa+1 | Sa+1 , Sb+1 | Sb+1 , Sa+1 ; ACK ->    (Sa+1, Sb+1)
# Sa+1 , Sb+1 | Sb+1 , Sa+1 | Sa+1 , Sb+1 | Sb+1 , Sa+1 ; -> ACK    (Sa+1, Sb+1)

            if src_conn.get("state") == "SYN-SENT":
                src_conn["state"] = "ESTABLISHED"
                print "established", src
                # Reply with ACK and forward SYNACK 
                yield self.write_packet(src, src_conn, flags="A")
                
                # Forward SYNACK
                dst_conn["state"] = "SYN-RECIEVED"
                yield self.write_packet(dst, dst_conn, flags="SA")
                #yield self.prev_layer.write(dst, data)
            else:
                dst_conn["state"] = "SYN-SENT"
                # Forward SYN
                #yield self.prev_layer.write(dst, data)
                yield self.write_packet(dst, dst_conn, flags="S")
            passthru = False

        if pkt_tcp.flags & dpkt.tcp.TH_ACK:
            if src_conn.get("state") == "SYN-RECIEVED":
                src_conn["state"] = "ESTABLISHED"
                print "established", src
            if src_conn.get("state") == "ESTABLISHED":
                src_conn["seq"] = pkt_tcp.ack

        if commit:
            self.connections[conn_id] = conn

        #print src, repr(pkt)
        #print repr(str(pkt))

        if passthru:
            yield self.passthru(src, data)

    @gen.coroutine
    def write_packet(self, dst, conn, flags="A"):
        payload = None
        seq = conn["seq"]
        ack = conn.get("ack", 0)
        if conn["out_buffer"]:
            payload = conn["out_buffer"][:1400]
            conn["out_buffer"] = conn["out_buffer"][1400:]
            flags += "P"
            conn["unacked"].append((seq, payload))
            conn["seq"] += len(payload)

        bflags = tcp_dump_flags(flags)
        ts_val = struct.pack("I", conn["ts_val"])
        ts_ecr = struct.pack("I", conn["ts_ecr"])
        tcp_opts = tcp_dump_opts([
            (dpkt.tcp.TCP_OPT_TIMESTAMP, ts_val + ts_ecr)
        ])
        pkt = dpkt.ethernet.Ethernet(
            dst=conn["eth_dst"],
            src=conn["eth_src"],
            type=dpkt.ethernet.ETH_TYPE_IP
        )
        ip_pkt = dpkt.ip.IP(
            id=0,
            dst=conn["ip_dst"],
            src=conn["ip_src"],
            p=dpkt.ip.IP_PROTO_TCP
        )
        tcp_pkt = dpkt.tcp.TCP(
            sport=conn["sport"],
            dport=conn["dport"],
            seq=seq,
            ack=ack,
            flags=bflags,
        )
        tcp_pkt.opts = tcp_opts
        tcp_pkt.off += len(tcp_opts) / 4
        if payload is not None:
            tcp_pkt.data = payload

        ip_pkt.data = tcp_pkt
        ip_pkt.len += len(tcp_pkt)

        pkt.data = ip_pkt

        data = str(pkt)
        if self.prev_layer is not None:
            print ">", dst, seq, ack, flags, ((len(payload), payload[:8]) if payload else None)
            yield self.prev_layer.write(dst, data)

    @gen.coroutine
    def write(self, dst, data, conn_id):
        if conn_id[::-1] in self.connections:
            conn_id = conn_id[::-1]
        conn = self.connections[conn_id]
        dst_conn = conn[dst]
        dst_conn["out_buffer"] += data
        yield self.write_packet(dst, dst_conn, flags="A")


