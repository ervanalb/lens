import dpkt
from ethernet import NetLayer

import tornado.gen as gen

class IPv4Layer(NetLayer):
    NAME = "ip"
    IN_TYPES = {"Ethernet"}
    OUT_TYPE = "IP"

    @staticmethod
    def pretty_ip(ip):
        return ".".join([str(ord(x)) for x in ip])
    @staticmethod
    def wire_ip(ip):
        return "".join([chr(int(x)) for x in ip.split(".")])

    def __init__(self):
        self.next_id = 0
        super(IPv4Layer, self).__init__()

    def match(self, src, header):
        return header["eth_type"] == dpkt.ethernet.ETH_TYPE_IP

    # coroutine
    def on_read(self, src, header, payload):
        # It already comes parsed by dpkt from EthernetLayer
        #pkt = dpkt.ip.IP(payload) 
        #print "IP>", payload
        pkt = payload 
        header["ip_id"] = pkt.id
        header["ip_dst"] = dst_ip = self.pretty_ip(pkt.dst)
        header["ip_src"] = src_ip = self.pretty_ip(pkt.src)
        header["ip_p"] = pkt.p
        return self.bubble(src, header, pkt.data)

    # coroutine
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
        return self.write_back(dst, header, str(pkt))

class IPv4FilterLayer(NetLayer):
    NAME = "ipv4_filter"
    """ Pass all IPv4 packets with a given IP through """
    IN_TYPES = {"IP"}
    OUT_TYPE = "IP"

    def __init__(self, ips = []):
        super(IPv4FilterLayer, self).__init__()
        self.ips = ips

    def match(self, src, header):
        return header["ip_src"] in self.ips or header["ip_dst"] in self.ips

