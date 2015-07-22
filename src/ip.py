import dpkt
import ethernet 

import tornado.gen as gen

class IPv4Layer(ethernet.NetLayer):
    IN_TYPES = {"Ethernet"}
    OUT_TYPE = "IP"

    SINGLE_CHILD = False

    @staticmethod
    def pretty_ip(ip):
        return ".".join([str(ord(x)) for x in ip])
    @staticmethod
    def wire_ip(ip):
        return "".join([chr(int(x)) for x in ip.split(".")])

    def __init__(self, addr_filter=None):
        self.addr_filter = addr_filter
        self.next_id = 0
        super(IPv4Layer, self).__init__()

    def match_child(self, src, header, key):
        return key == header["ip_p"]

    @gen.coroutine
    def on_read(self, src, header, payload):
        # It already comes parsed by dpkt from EthernetLayer
        #pkt = dpkt.ip.IP(payload) 
        #print "IP>", payload
        pkt = payload 
        header["ip_id"] = pkt.id
        header["ip_dst"] = dst_ip = self.pretty_ip(pkt.dst)
        header["ip_src"] = src_ip = self.pretty_ip(pkt.src)
        header["ip_p"] = pkt.p
        if self.addr_filter is None or src_ip in self.addr_filter or dst_ip in self.addr_filter:
            yield self.bubble(src, header, pkt.data)
        else:
            yield self.passthru(src, header, payload)

    @gen.coroutine
    def write(self, dst, header, payload):
        pkt = dpkt.ip.IP(
                id=header.get("ip_id", self.next_id),
                dst=self.wire_ip(header["ip_dst"]),
                src=self.wire_ip(header["ip_src"]),
                p=header["ip_p"])
        if "ip_id" not in header:
            self.next_id = (self.next_id + 1) & 0xFFFF
        pkt.data = payload
        pkt.len += len(payload)
        yield self.write_back(dst, header, str(pkt))

