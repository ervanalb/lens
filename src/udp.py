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
        pkt = dpkt.udp.UDP(sport=header["udp_sport"], dport=header["udp_dport"])
        pkt.data = data 
        pkt.ulen = len(pkt)

        # Return dpkt.udp.UDP instance so IP layer can calc checksum
        yield self.write_back(dst, header, data)


class UDPAppLayer(NetLayer):
    PORT = 40000

class UDPCopyLayer(UDPAppLayer):
    def __init__(self, *args, **kwargs):
        super(UDPCopyLayer, self).__init__(*args, **kwargs)
        self.f = open('/tmp/udp%d' % self.PORT, 'w')

    @gen.coroutine
    def on_read(self, src, header, data):
        self.f.write(data)



class UDPVideoLayer(UDPAppLayer):
    TRANSCODE = ["/usr/bin/ffmpeg", "-y", "-i",  "pipe:0", "-vf", "negate, vflip", "-f", "h264", "pipe:1"]
    UNIT = "\x00\x00\x00\x01"
    PS = 1396

    def __init__(self, *args, **kwargs):
        log_prefix = kwargs.pop('log_prefix', None)
        self.passthrough = kwargs.pop("passthrough", False)

        super(UDPVideoLayer, self).__init__(*args, **kwargs)
        
        if log_prefix is not None:
            self.log_raw = open(log_prefix + ".raw", 'w')
            self.log_input = open(log_prefix + ".input", 'w')
            self.log_output = open(log_prefix + ".output", 'w')
        else:
            self.log_raw = None
            self.log_input = None
            self.log_output = None

        self.ffmpeg = subprocess.Popen(self.TRANSCODE, stdout=subprocess.PIPE, stdin=subprocess.PIPE)
        fcntl.fcntl(self.ffmpeg.stdout.fileno(), fcntl.F_SETFL, os.O_NONBLOCK)


        self.seq = 0
        self.ts = 0
        self.fu_start = False
        self.rencoded_buffer = ""

    @gen.coroutine
    def on_read(self, src, header, data):
        if self.log_raw is not None:
            self.log_raw.write(data)
            self.log_raw.flush()
        if self.passthrough:
            self.bubble(src, header, data)
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
                #print "writing packet to ffmpeg"
                if self.log_input is not None:
                    self.log_input.write(nout)
                    self.log_input.flush()
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
                yield self.write_nal_fragment(src, header, '\x7C' + chr(0x80 | (h0 & 0x1F)) + nal_data[:self.PS-2], end=False)
                nal_data = nal-data[self.PS-2:]
                while len(nal_data) > self.PS-2:
                    yield self.write_nal_fragment(src, header, '\x7C' + chr(0x00 | (h0 & 0x1F)) + nal_data[:self.PS-2], end=False)
                    nal_data = nal-data[self.PS-2:]
                yield self.write_nal_fragment(src, header, '\x7C' + chr(0x40 | (h0 & 0x1F)) + nal_data, end=False)

    @gen.coroutine
    def write_nal_fragment(self, src, header, data, end=True):
        print "writing nal to dst"
        dst = self.route(src)
        mark = 0x80 if end else 0 
        head = struct.pack("!BBHII", 0x80, 96 | mark, self.seq, self.ts, 0)
        self.seq += 1
        if self.log_output is not None:
            self.log_output.write(head + data)
            self.log_output.flush()
        if not self.passthrough:
            yield self.write_back(dst, header, head + data)


