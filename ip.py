import dpkt
import ethernet 

import tornado.gen as gen

class IPv4Layer(ethernet.NetLayer):
    IN_TYPES = {"Ethernet"}
    OUT_TYPE = "IP"

    @staticmethod
    def pretty_ip(ip):
        return ".".join([str(ord(x)) for x in ip])
    @staticmethod
    def wire_ip(ip):
        return "".join([chr(int(x)) for x in ip.split(".")])

    def __init__(self, prev_layer=None, next_layer=None, addr_filter=None):
        self.prev_layer = prev_layer
        self.next_layer = next_layer
        self.addr_filter = addr_filter
        self.next_id = 0

    @gen.coroutine
    def on_read(self, src, payload, header):
        if header["eth_type"] == dpkt.ethernet.ETH_TYPE_IP:
            #pkt = dpkt.ip.IP(payload)
            pkt = payload
            header["ip_id"] = pkt.id
            header["ip_dst"] = dst_ip = self.pretty_ip(pkt.dst)
            header["ip_src"] = src_ip = self.pretty_ip(pkt.src)
            header["ip_p"] = pkt.p
            if self.addr_filter is None or src_ip in self.addr_filter or dst_ip in self.addr_filter:
                #print src, repr(pkt)
                yield self.bubble(src, pkt.data, header)
        else:
            yield self.passthru(src, payload, header)

    @gen.coroutine
    def write(self, dst, payload, header):
        pkt = dpkt.ip.IP(
                id=header.get("ip_id", self.next_id),
                dst=self.wire_ip(header["ip_dst"]),
                src=self.wire_ip(header["ip_src"]),
                p=header["ip_p"])
        if "ip_id" not in header:
            self.next_id = (self.next_id + 1) & 0xFFFF
        pkt.data = payload
        pkt.len += len(payload)
        yield self.prev_layer.write(dst, str(pkt), header)

