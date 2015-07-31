import collections
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
        self.next_id = 0

        self.seen_ips = collections.defaultdict(set)
        self.passthru_ips = set()
        self.filter_ips = set()
        self.block_ips = set()

        if addr_filter is not None:
            self.fitler_ips = set(addr_filter)

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

        self.seen_ips[src_ip].add(header["eth_src"])
        self.seen_ips[dst_ip].add(header["eth_dst"])

        match = lambda ip_list: ip_list is None or src_ip in ip_list or dst_ip in ip_list

        if match(self.block_ips):
            pass # Drop the packet -- maybe we should respond with an ICMP message?
        elif match(self.passthru_ips):
            yield self.passthru(src, header, payload)
        elif match(self.filter_ips);
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

    def do_help(self):
        return """Ethernet Layer:
        help - print this message
        list - list IP addresses seen & corresponding MAC addresses
        status - print current status
        passthru - set an IP address to 'passthru' mode
        passthru all - make the default behavior passthru
        unpassthru -
        block - Silently drop packets of given IP
        unblock -
        filter - Pass packets on to next layer(s)
        unfilter -
        """

    def do_list(self):
        output = ""
        for ip, macs in self.seen_ips.items():
            output += "%s\t%s\n" % (ip, "\t".join(macs))
        return output

    do_passthru, do_unpassthru = make_list_commands("passthru_ips")
    def do_passthru(self, ip):

def make_list_commands(list_name):
    def do_add(self, ip):
        list_obj = getattr(self, list_name)
        if ip.lower() == "all":
            list_obj
        elif list_obj is None:
            list_obj = {ip}
        else:
            list_obj.add(ip)
    def do_rm(self, ip):
        list_obj = getattr(self, list_name)
        if ip.lower() == "all":
            list_obj
        elif list_obj is None:
            list_obj = {ip}
        else:
            list_obj.add(ip)
    return do_add, do_rm
