from base import NetLayer

import dpkt 

from tornado import gen

class UDPLayer(NetLayer):
    IN_TYPES = {"IP"}
    OUT_TYPE = "IP"
    SINGLE_CHILD = False
    
    seen_ports = set()

    def match_child(self, src, header, key):
        return key == header["udp_dport"] or key == header["udp_sport"]

    @gen.coroutine
    def on_read(self, src, header, data):
        pkt = data

        header["udp_sport"] = pkt.sport
        header["udp_dport"] = pkt.dport

        yield self.bubble(src, header, pkt.data)

    @gen.coroutine
    def write(self, dst, header, data):
        header["ip_p"] = dpkt.ip.IP_PROTO_UDP
        pkt = dpkt.udp.UDP(sport=header["udp_sport"], dport=header["udp_dport"])
        pkt.data = data 
        pkt.ulen = len(pkt)

        # Return dpkt.udp.UDP instance so IP layer can calc checksum
        yield self.write_back(dst, header, pkt)
