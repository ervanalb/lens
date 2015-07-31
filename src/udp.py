from base import NetLayer

import dpkt 

from tornado import gen

class UDPLayer(NetLayer):
    NAME = "udp"
    IN_TYPES = {"IP"}
    OUT_TYPE = "IP"
    seen_ports = set()

    def match(self, src, header):
        return header["ip_p"] == dpkt.ip.IP_PROTO_UDP

    # coroutine
    def on_read(self, src, header, data):
        pkt = data

        header["udp_sport"] = pkt.sport
        header["udp_dport"] = pkt.dport

        return self.bubble(src, header, pkt.data)

    # coroutine
    def write(self, dst, header, data):
        header["ip_p"] = dpkt.ip.IP_PROTO_UDP
        pkt = dpkt.udp.UDP(sport=header["udp_sport"], dport=header["udp_dport"])
        pkt.data = data 
        pkt.ulen = len(pkt)

        # Return dpkt.udp.UDP instance so IP layer can calc checksum
        return self.write_back(dst, header, pkt)

class UDPFilterLayer(NetLayer):
    NAME = "udp_filter"
    """ Pass all UDP packets with a given port through """
    IN_TYPES = {"UDP"}
    OUT_TYPE = "UDP"

    def __init__(self, ports = []):
        super(UDPFilterLayer, self).__init__()
        self.ports = ports

    def match(self, src, header):
        return header["udp_dport"] in self.ports or header["udp_sport"] in self.ports
