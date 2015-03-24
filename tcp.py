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

hosts = {
    "18.238.0.97": "H",
    "18.111.96.68": "Z",
    "18.238.7.58": "D"
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
def connection_id(pkt, header):
    # Generate a tuple representing the stream 
    # (source host addr, source port, dest addr, dest port)
    return ((header["ip_src"], pkt.sport),
            (header["ip_dst"], pkt.dport))

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
                print "timebase: reset"
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

class TCPPassthruLayer(NetLayer):
    """ Simple TCP layer which will pass packets on certain TCP ports through """
    IN_TYPES = {"IP"}
    OUT_TYPE = "IP"
    def __init__(self, prev_layer=None, next_layer=None, ports=None):
        self.prev_layer = prev_layer
        self.next_layer = next_layer
        self.ports = ports

    @gen.coroutine
    def on_read(self, src, payload, header):
        if header.get("eth_type") != dpkt.ethernet.ETH_TYPE_IP or header.get("ip_p") != dpkt.ip.IP_PROTO_TCP:
            yield self.passthru(src, payload, header)
            return 

        #try:
        #    pkt = dpkt.tcp.TCP(payload)
        #except dpkt.NeedData:
        #    return
        pkt = payload

        if pkt.sport in self.ports or pkt.dport in self.ports:
            yield self.passthru(src, payload, header)
        else:
            yield self.bubble(src, payload, header)

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
    IN_TYPES = {"IP"}
    OUT_TYPE = "TCP"
    def __init__(self, next_layer=None, prev_layer=None, debug=True):
        self.next_layer = next_layer # next_layer is a *factory*
        self.prev_layer = prev_layer
        self.connections = {}
        self.debug = debug
        self.timers = collections.defaultdict(TimestampEstimator)

    @gen.coroutine
    def on_read(self, src, payload, header):
        if self.prev_layer is None or self.next_layer is None:
            yield self.passthru(src, payload, header)
            return 

        if header.get("eth_type") != dpkt.ethernet.ETH_TYPE_IP or header.get("ip_p") != dpkt.ip.IP_PROTO_TCP:
            yield self.passthru(src, payload, header)
            return 

        pkt = payload

        #TODO: validate checksums / packet

        tcp_opts = dpkt.tcp.parse_opts(pkt.opts)
        tcp_opts_dict = dict(tcp_opts)

        dst = self.route(src)
        #conn_id = connection_id(pkt)
        conn_id = connection_id(pkt, header)
        if conn_id[::-1] in self.connections: # is_receiver
            # The connection was initiated by the dst
            conn_id = conn_id[::-1]
            sender, receiver = dst, src 
        else:
            sender, receiver = src, dst

        # For now, assume that connections are symmetric
        conn = self.connections.get(conn_id, {src: {}, dst: {}, "count": len(self.connections)})
        self.connections[conn_id] = conn

        src_conn = conn[src]
        dst_conn = conn[dst]
        sender_conn = conn[sender]
        receiver_conn = conn[receiver]
        if "next_layer" not in conn:
            conn["next_layer"] = self.next_layer(conn=conn, prev_layer=self)
        next_layer = conn["next_layer"]

        host_ip = header["ip_src"]
        dest_ip = header["ip_dst"]

        # Update timestamps
        if dpkt.tcp.TCP_OPT_TIMESTAMP in tcp_opts_dict:
            ts_val, ts_ecr = struct.unpack('!II', tcp_opts_dict[dpkt.tcp.TCP_OPT_TIMESTAMP])
            dst_conn['last_ts_val'] = dst_conn.get('ts_val', 0)
            #dst_conn['ts_val'] = ts_val
            src_conn['ts_ecr'] = ts_val
            t = self.timers[host_ip].get_time()
            print src, ts_val, t, '%', (ts_val - t) / (ts_val + 0.1) * 100
            self.timers[host_ip].put_sample(ts_val)
        else:
            ts_val, ts_ecr = None, None

        if self.debug:
            print "TCP {}{} {} {:.3f} {}:{:<5}->{}:{:<5} {:<4} seq={:<3} ({:<10}) ack={:<3} ({:<10}) data=[{:<4}]{:8} tsval={} tsecr={}".format(
                    "AB"[src], "->",
                    conn["count"],
                    time.clock(), 
                    hosts.get(host_ip, "?"),
                    pkt.sport,
                    hosts.get(dest_ip, "?"),
                    pkt.dport,
                    tcp_read_flags(pkt.flags),
                    pkt.seq - dst_conn['seq_start'] if 'seq_start' in dst_conn else '-',
                    pkt.seq,
                    pkt.ack - src_conn['seq_start'] if pkt.flags & dpkt.tcp.TH_ACK and 'seq_start' in src_conn else '-',
                    pkt.ack if pkt.flags & dpkt.tcp.TH_ACK else '-',
                    len(pkt.data),
                    pkt.data.replace("\n", "\\n")[:8] if pkt.data else None,
                    ts_val,
                    ts_ecr
                )

        if tcp_has_payload(pkt):
            if src_conn.get("state") == "ESTABLISHED":
                data = pkt.data
                src_conn["in_buffer"] += data
                src_conn["ack"] += len(data)

                # Bubble up data to next layer
                yield next_layer.on_read(src, data)

                # ACK the data
                yield self.write_packet(src, src_conn, flags="A")


        if pkt.flags & dpkt.tcp.TH_SYN:
            # Assume we aren't redirecting the traffic, just modifying the contents

            dst_conn["ip_header"] = header
            dst_conn["ip_src"] = host_ip
            dst_conn["ip_dst"] = dest_ip
            dst_conn["sport"] = pkt.sport
            dst_conn["dport"] = pkt.dport
            dst_conn["win"] = pkt.win

            dst_conn["out_buffer"] = ""
            dst_conn["in_buffer"] = ""
            dst_conn["unacked"] = []

            dst_conn["seq"] = pkt.seq
            src_conn["ack"] = pkt.seq + 1

            # For relative sequence nums
            dst_conn["seq_start"] = pkt.seq 
            src_conn["ack_start"] = pkt.seq


# A           | D_sender    | D_reciever  | B
# ------------------------------------------------------------
# Connection setup: A sends a SYN packet
# SYN-SENT    |             | SYN-SENT    |             ; -> SYN ->
# SYN-SENT    | SYN-RECV    | ESTABLISHED | SYN-RECV    ; SYNACK <-
# ESTABLISHED | SYN-RECV    | ESTABLISHED | SYN-RECV    ; <- SYNACK
# ESTABLISHED | SYN-RECV    | ESTABLISHED | ESTABLISHED ; ACK ->
# ESTABLISHED | ESTABLISHED | ESTABLISHED | ESTABLISHED ; -> ACK
# A sends a RST packet on an ESTABLISHED connection 
# CLOSED      | RESET       | CLOSED      | ESTABLISHED ; RST -> 
# CLOSED      | RESET       | CLOSED      | RESET       ; -> RST
# A sends a FIN packet on an ESTABLISHED connection
# (TODO)

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
                # The ACK reply gets handled later on
                
                # Forward SYNACK
                dst_conn["state"] = "SYN-RECIEVED"
                yield self.write_packet(dst, dst_conn, flags="SA")
            else:
                dst_conn["state"] = "SYN-SENT"
                # Forward SYN
                yield self.write_packet(dst, dst_conn, flags="S")

        if pkt.flags & dpkt.tcp.TH_FIN:
            print "FIN", sender_conn.get('state'), receiver_conn.get('state'), src_conn.get('state')
            if src_conn.get("state") == "ESTABLISHED":
                src_conn["ack"] += 1
                src_conn["state"] = "LAST-ACK"
                if dst_conn.get("state") == "ESTABLISHED":
                    dst_conn["state"] = "FIN-WAIT-1"
                    # Forward FIN
                    yield self.write_packet(dst, dst_conn, flags="FA")
                    dst_conn["seq"] += 1

                # Reply with FINACK 
                yield self.write_packet(src, src_conn, flags="FA")
                src_conn["seq"] += 1 

            elif src_conn.get("state") == "FIN-WAIT-1":
                src_conn["ack"] += 1
                src_conn["state"] = "CLOSED"

                # Reply with ACK 
                yield self.write_packet(src, src_conn, flags="A")

                # Bubble up close event
                yield next_layer.on_close(src)
                #TODO: prune connection obj

        elif pkt.flags & dpkt.tcp.TH_ACK:
            if src_conn.get("state") == "SYN-RECIEVED":
                src_conn["state"] = "ESTABLISHED"
                print "established", src

            if src_conn.get("state") == "ESTABLISHED":
                src_conn["seq"] = max(src_conn.get('seq'), pkt.ack)
                # We don't need to ACK the ACK unless it's a SYNACK
                if pkt.flags & dpkt.tcp.TH_SYN:
                    yield self.write_packet(src, src_conn, flags="A")

            if src_conn.get("state") == "LAST-ACK":
                src_conn["state"] = "CLOSED"

                # Bubble up close event
                yield next_layer.on_close(src)
                #TODO: prune connection obj


        if pkt.flags & dpkt.tcp.TH_RST:
            if "state" in src_conn and dst_conn.get("state"): # If it's already been reset, just passthru
                # This is a connection we're modifying
                print "RST on MiTM connection", src_conn["state"], dst_conn.get("state")
                dst_conn["state"] = "RESET"
                src_conn["state"] = "CLOSED"
                if "seq" not in dst_conn:
                    print 'invalid RST', dst_conn
                if 'seq' in dst_conn:
                    # Forward RST
                    yield self.write_packet(dst, dst_conn, flags="R")
                else:
                    yield self.passthru(src, payload, header)

                # Bubble up close event
                yield next_layer.on_close(src)
                #TODO: prune connection obj
            else:
                # This isn't on a actively modified connection, passthru
                print "RST passthru"
                yield self.passthru(src, payload, header)

        if "state" not in dst_conn: # Not handled
            yield self.passthru(src, payload, header)

    @gen.coroutine
    def write_packet(self, dst, conn, flags="A"):
        header = conn["ip_header"]
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
        estimated_ts_val = self.timers[conn["ip_src"]].get_time()
        if estimated_ts_val is None or estimated_ts_val == 0:
            estimated_ts_val = conn.get("last_ts_val", 0)
        ts_val = struct.pack("!I", estimated_ts_val)
        ts_ecr = struct.pack("!I", conn.get("ts_ecr", 0))
        tcp_opts = tcp_dump_opts([
            (dpkt.tcp.TCP_OPT_TIMESTAMP, ts_val + ts_ecr)
        ])
        pkt = dpkt.tcp.TCP(
            sport=conn["sport"],
            dport=conn["dport"],
            seq=seq,
            ack=ack,
            flags=bflags,
            win=conn.get("win", dpkt.tcp.TCP_WIN_MAX),
        )
        pkt.opts = tcp_opts
        pkt.off += len(tcp_opts) / 4
        if payload is not None:
            pkt.data = payload

        if self.debug:
            print "TCP {}{}   {:.3f} {}:{:<5}->{}:{:<5} {:<4} seq={:<3} ({:<10}) ack={:<3} ({:<10}) data=[{:<4}]{:8} tsval={} tsecr={}".format(
                    "->", "AB"[dst],
                    time.clock(), 
                    hosts.get(header["ip_src"], "?"),
                    pkt.sport,
                    hosts.get(header["ip_dst"], "?"),
                    pkt.dport,
                    tcp_read_flags(pkt.flags),
                    pkt.seq - conn['seq_start'] if 'seq_start' in conn else '-',
                    pkt.seq,
                    pkt.ack - conn['ack_start'] if pkt.flags & dpkt.tcp.TH_ACK and 'ack_start' in conn else '-',
                    pkt.ack if pkt.flags & dpkt.tcp.TH_ACK else '-',
                    len(pkt.data),
                    pkt.data.replace("\n", "\\n")[:8] if pkt.data else None,
                    conn.get('ts_val', 0),
                    conn.get('ts_ecr', 0)
                )
        # Don't stringify packet so the IP layer can calculate the checksum for us
        yield self.prev_layer.write(dst, pkt, header)

    @gen.coroutine
    def write_conn(self, dst, data, conn):
        dst_conn = conn[dst]
        dst_conn["out_buffer"] += data
        yield self.write_packet(dst, dst_conn, flags="A")

    @gen.coroutine
    def write(self, dst, data, header):
        yield self.write_conn(dst, data, header)
        
class TCPApplicationLayer(NetLayer):
    IN_TYPES = {"TCP"}
    OUT_TYPE = "TCP App"
    def __init__(self, conn, prev_layer, next_layer=None):
        self.conn = conn
        self.prev_layer = prev_layer
        self.next_layer = next_layer

    @gen.coroutine
    def bubble(self, src, data, *args):
        if self.next_layer is not None:
            yield self.next_layer.on_read(src, data, *args)
        else:
            yield self.prev_layer.write_conn(self.route(src), data, self.conn)
        
    @gen.coroutine
    def on_read(self, src, data, *args):
        yield self.bubble(src, data, *args)

    @gen.coroutine
    def on_close(self, src, *args):
        if self.next_layer is not None:
            yield self.next_layer.on_close(src, *args)

    @gen.coroutine
    def write_conn(self, dst, data, conn, *args):
        # `conn` is actually just ignored, which is odd #FIXME
        yield self.prev_layer.write_conn(dst, data, self.conn, *args)

    @gen.coroutine
    def write(self, dst, data, *args):
        yield self.prev_layer.write(dst, data, self.conn, *args)


