import dpkt
import tornado.gen as gen
from base import NetLayer

class EthernetLayer(NetLayer):
    NAME = "eth"

    def __init__(self, *args, **kwargs):
        super(EthernetLayer, self).__init__(*args, **kwargs)
        self.seen_macs = {k: set() for k in self.routing.keys()}

    @staticmethod
    def pretty_mac(mac):
        return ":".join(["{:02x}".format(ord(x)) for x in mac])
    @staticmethod
    def wire_mac(mac):
        return "".join([chr(int(x, 16)) for x in mac.split(":")])

    @gen.coroutine
    def on_read(self, src, header, data):
        try:
            pkt = dpkt.ethernet.Ethernet(data)
        except dpkt.NeedData:
            yield self.passthru(src, header, data)
            return
        header = {
            "eth_dst": self.pretty_mac(pkt.dst),
            "eth_src": self.pretty_mac(pkt.src),
            "eth_type": pkt.type,
        }
        self.seen_macs[src].add(header["eth_src"])
        yield self.bubble(src, header, pkt.data)

    @gen.coroutine
    def write(self, dst, header, payload):
        pkt = dpkt.ethernet.Ethernet(
                dst=self.wire_mac(header["eth_dst"]),
                src=self.wire_mac(header["eth_src"]),
                type=header["eth_type"],
                data=payload)
        yield self.write_back(dst, header, str(pkt))

    def do_list(self):
        """List MAC addresses that have sent data to attached NICs."""
        output = ""
        for src, macs in self.seen_macs.items():
            output += "Source %d:\n" % src
            for mac in macs:
                output += " - %s\n" % mac
        return output

