import collections
import dpkt
from base import NetLayer

import tornado.gen as gen

#def make_list_commands(list_name):
#    def do_add(self, ip=None):
#        list_obj = getattr(self, list_name)
#        if ip.lower() == "all":
#            list_obj = None
#        elif list_obj is None:
#            list_obj = {ip}
#        else:
#            list_obj.add(ip)
#        setattr(self, list_name, list_obj)
#
#    def do_rm(self, ip=None):
#        list_obj = getattr(self, list_name)
#        if ip.lower() == "all":
#            list_obj.clear()
#        elif list_obj is None:
#            list_obj = {ip}
#        else:
#            list_obj.add(ip)
#        setattr(self, list_name, list_obj)
#    return do_add, do_rm

class IPv4Layer(NetLayer):
    NAME = "ip"

    @staticmethod
    def pretty_ip(ip):
        return ".".join([str(ord(x)) for x in ip])
    @staticmethod
    def wire_ip(ip):
        return "".join([chr(int(x)) for x in ip.split(".")])

    def __init__(self):
        self.next_ids = {}
        self.seen_ips = collections.defaultdict(set)
        self.protocol_stats = collections.Counter()

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

        self.seen_ips[src_ip].add(header["eth_src"])
        self.seen_ips[dst_ip].add(header["eth_dst"])

        self.protocol_stats[pkt.p] += 1

        return self.bubble(src, header, pkt.data)

    # coroutine
    def write(self, dst, header, payload):
        src_mac = header["eth_src"]
        if src_mac not in self.next_ids:
            # Keep track of per-MAC IP packet ID's
            # Generate one randomly if we need to
            self.next_ids[src_mac] = header.get("ip_id", random.randint(0, 0xFFFF))

        pkt = dpkt.ip.IP(
                id=self.next_ids[src_mac],
                dst=self.wire_ip(header["ip_dst"]),
                src=self.wire_ip(header["ip_src"]),
                p=header["ip_p"])

        self.next_ids[src_mac] = (self.next_ids[src_mac] + 1) & 0xFFFF
        pkt.data = payload
        pkt.len += len(payload)

        return self.write_back(dst, header, str(pkt))
    
    def do_protos(*args):
        """List statistics about protocols."""
        for protocol, count in self.protocol_stats.most_common():
            try:
                print " {} - {}".format(count, dpkt.ip.IP.get_proto(protocol).__name__)
            except KeyError:
                print " {} - ({})".format(count, protocol)

class IPv4FilterLayer(NetLayer):
    """ Pass all IPv4 packets with a given IP through """
    NAME = "ipv4_filter"

    def __init__(self, ips=None):
        super(IPv4FilterLayer, self).__init__()
 
        if ips is None:
            ips = []
        self.ips = ips

    def match(self, src, header):
        return header["ip_src"] in self.ips  or header["ip_dst"] in self.ips
