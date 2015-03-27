from ethernet import NetLayer

import dpkt 

from tornado import gen
import struct
import subprocess
import fcntl
import os

class UDPLayer(NetLayer):
    IN_TYPES = {"IP"}
    OUT_TYPE = "IP"

    def __init__(self, prev_layer=None):
        self.prev_layer = prev_layer
        self.apps = {}

    def register_app(self, handler):
        self.apps[handler.PORT] = handler()

    @gen.coroutine
    def on_read(self, src, data, header):
        pkt = data

        if header.get("eth_type") != dpkt.ethernet.ETH_TYPE_IP or header.get("ip_p") != dpkt.ip.IP_PROTO_UDP:
            yield self.passthru(src, data, header)
            return 

        header["udp_sport"] = pkt.sport
        header["udp_dport"] = pkt.dport

        if pkt.sport in self.apps:
            yield self.apps[pkt.sport].on_read(src, pkt.data, header)
        if pkt.dport in self.apps:
            yield self.apps[pkt.dport].on_read(src, pkt.data, header)
        #elif pkt.sport not in self.apps:
        yield self.passthru(src, data, header)

    @gen.coroutine
    def write(self, dst, data, header):
        if "udp_sport" in header and "udp_dport" in header:
            pkt = dpkt.udp.UDP(sport=header["udp_sport"], dport=header["udp_dport"])
            pkt.data = data 
            pkt.ulen = len(pkt)

            # Return dpkt.udp.UDP instance so IP layer can calc checksum
            yield pkt 
        else:
            yield self.prev_layer.write(dst, data, header)


class UDPAppLayer(NetLayer):
    PORT = 40000

class UDPCopyLayer(UDPAppLayer):
    def __init__(self, *args, **kwargs):
        super(UDPCopyLayer, self).__init__(*args, **kwargs)
        self.f = open('/tmp/udp%d' % self.PORT, 'w')

    @gen.coroutine
    def on_read(self, src, data, header):
        if header["udp_sport"] == self.PORT:
            self.f.write(data)



class UDPVideoLayer(UDPAppLayer):
    TRANSCODE = ["/usr/bin/ffmpeg", "-y", "-i",  "pipe:0", "-vf", "negate, vflip", "-f", "h264", "pipe:1"]
    UNIT = "\x00\x00\x00\x01"
    PS = 1396

    def __init__(self, *args, **kwargs):
        super(UDPVideoLayer, self).__init__(*args, **kwargs)
        #self.out = open('/tmp/udp%d' % self.PORT, 'w')
        self.ffmpeg = subprocess.Popen(self.TRANSCODE, stdout=subprocess.PIPE, stdin=subprocess.PIPE)
        fcntl.fcntl(self.ffmpeg.stdout.fileno(), fcntl.F_SETFL, os.O_NONBLOCK)
        self.seq = 0
        self.ts = 0
        self.fu_start = False
        self.rencoded_buffer = ""

    @gen.coroutine
    def on_read(self, src, data, header):
        if header["udp_sport"] == self.PORT:
            if len(data) >= 12: #and data[0x2b] == '\xe0':
                h, d = data[:12], data[12:]
                flags, prot, seq, ts, ident = struct.unpack("!BBHII", h)
                self.ts = ts
                flags |= (prot & 0x80) << 1
                prot &= 0x7F
                if prot == 96:
                    #print 'match', seq, ts, ident, flags, len(d)
                    nalu = d
                    n0 = ord(nalu[0])
                    n1 = ord(nalu[1])
                    nout = self.UNIT + nalu
                    if n0 & 0x10:
                        if n0 != 0x7C: raise Exception("Invalid fragmentation format: %d 0x%x" % (n0 & 0x1F, n0))
                        if n1 & 0x80:
                            if self.fu_start: raise Exception("Restarted fragment")
                            self.fu_start = True
                            nout = self.UNIT + chr((n0 & 0xE0) | (n1 & 0x1F)) + nalu[2:]
                        else:
                            if self.fu_start:
                                nout = nalu[2:]
                                if n1 & 0x40:
                                    self.fu_start = False
                            else:
                                print "skipping packet :("
                    print "writing packet to ffmpeg"
                    self.ffmpeg.stdin.write(nout)
                    yield self.pass_on(src, header)
                else:
                    print "no match", prot, seq, ts, ident, flags, len(d)

    @gen.coroutine
    def pass_on(self, src, header):
        try:
            self.rencoded_buffer += self.ffmpeg.stdout.read()
        except IOError:
            return
        print "got data from ffmpeg"
        usplit = self.rencoded_buffer.split(self.UNIT)
        assert usplit[0] == ''
        self.rencoded_buffer = usplit[-1]
        for nal_data in usplit[1:-1]:
            if len(nal_data) <= self.PS:
                yield self.write_nal_fragment(src, nal_data, header, end=True)
            else:
                #FU-A fragmentation
                h0 = ord(nal_data[0])
                yield self.write_nal_fragment(src, '\x7C' + chr(0x80 | (h0 & 0x1F)) + nal_data[:self.PS-2], header, end=False)
                nal_data = nal-data[self.PS-2:]
                while len(nal_data) > self.PS-2:
                    yield self.write_nal_fragment(src, '\x7C' + chr(0x00 | (h0 & 0x1F)) + nal_data[:self.PS-2], header, end=False)
                    nal_data = nal-data[self.PS-2:]
                yield self.write_nal_fragment(src, '\x7C' + chr(0x40 | (h0 & 0x1F)) + nal_data, header, end=False)

    @gen.coroutine
    def write_nal_fragment(self, src, data, header, end=True):
        print "writing nal to dst"
        dst = self.route(src)
        mark = 0x80 if end else 0 
        head = struct.pack("!BBHII", 0x80, 96 | mark, self.seq, self.ts, 0)
        self.seq += 1
        yield self.prev_layer.write(dst, head + data, header)


