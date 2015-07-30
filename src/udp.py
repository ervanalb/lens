from ethernet import NetLayer

import dpkt 

from tornado import gen
from tornado.ioloop import IOLoop
import struct
import subprocess
import fcntl
import os

def binprint(d):
    print " ".join(["{0:02x}".format(ord(c)) for c in d])

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
    #TRANSCODE = ["/usr/bin/ffmpeg", "-y", "-i",  "pipe:0", "-vf", "negate, vflip", "-f", "h264", "pipe:1"]
    TRANSCODE = ["/usr/bin/ffmpeg", "-y", "-f", "h264", "-i", "-", "-vf", "negate, vflip", "-f", "h264", "-"]
    TRANSCODE = ["/usr/bin/sh", "../misc/haxed.sh"]
    #TRANSCODE = ["tee","out.h264"]
    #TRANSCODE = ["cat"]
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
        self.vlog = open('/tmp/vout', 'w')
        self.vlog2 = open('/tmp/vout2', 'w')
        self.rlogi = open('/tmp/rlogi', 'w')
        self.rlogo = open('/tmp/rlogo', 'w')
        fcntl.fcntl(self.ffmpeg.stdout.fileno(), fcntl.F_SETFL, os.O_NONBLOCK)
        fcntl.fcntl(self.ffmpeg.stdin.fileno(), fcntl.F_SETFL, os.O_NONBLOCK)
        self.ioloop = IOLoop.instance()
        self.ioloop.add_handler(self.ffmpeg.stdout.fileno(), self.ffmpeg_read_handler, IOLoop.READ)

        self.seq = 0
        self.ts = 0
        self.fu_start = False
        self.rencoded_buffer = ''
        self.do_loop = False
        if self.do_loop:
            f = open("/tmp/voutff")
            self.templ = f.read()
        else:
            self.templ = "xxx"
        self.tp = self.templ
        #self.ffmpeg.stdin.write(self.templ)
        self.sent_iframe = False
        self.last_src = None
        self.last_header = None

    @gen.coroutine
    def on_read(self, src, header, data):
        #print "got video data", len(data)
        if self.log_raw is not None:
            self.log_raw.write(data)
            self.log_raw.flush()
        #if self.passthrough:
            #yield self.bubble(src, header, data)
        if len(data) >= 12: #and data[0x2b] == '\xe0':
            h, d = data[:12], data[12:]
            flags, prot, seq, ts, ident = struct.unpack("!BBHII", h)
            self.ts = ts
            flags |= (prot & 0x80) << 1
            prot &= 0x7F
            if prot == 96:
                self.last_src = src
                self.last_header = header
                #print 'match', seq, ts, ident, flags, len(d)
                nalu = d
                n0 = ord(nalu[0])
                n1 = ord(nalu[1])
                fragment_type = n0 & 0x1F
                if fragment_type < 24: # unfragmented
                    self.nout = self.UNIT + nalu
                    self.got_frame(self.nout)
                    if self.log_input is not None:
                        self.log_input.write(self.nout)
                        self.log_input.flush()
                elif fragment_type == 28: # FU-A
                    if n1 & 0x80:
                        if self.fu_start: print "Restarted fragment"
                        self.fu_start = True
                        self.nout = self.UNIT + chr((n0 & 0xE0) | (n1 & 0x1F)) + nalu[2:]
                    else:
                        if self.fu_start:
                            self.nout += nalu[2:]
                            if n1 & 0x40:
                                self.fu_start = False
                                self.got_frame(self.nout)
                                if self.log_input is not None:
                                    self.log_input.write(self.nout)
                                    self.log_input.flush()
                        else:
                            print "skipping packet :("

                #yield self.pass_on(src, header)
                #yield self.passthru(src, data, header)

    def got_frame(self, data):
        #print "incoming frame."
        if self.do_loop:
            self.ffmpeg.stdin.write(self.tp[:len(nout)])
            #self.ffmpeg.stdin.flush()
            self.tp = self.tp[len(nout):]
            if not self.tp:
                self.tp = self.templ
            self.vlog.write(data)
        else:
            try:
                self.ffmpeg.stdin.write(data)
                self.ffmpeg.stdin.flush()
            except IOError:
                print "ERROR! FFMPEG is too slow"
            self.vlog.write(data)

    def ffmpeg_read_handler(self, fd, events):
        new_data = self.ffmpeg.stdout.read()
        if new_data and self.last_src is not None and self.last_header is not None:
            f = self.pass_on(self.last_src, self.last_header, new_data)
            if f:
                self.ioloop.add_future(f, lambda f: None)

    @gen.coroutine
    def pass_on(self, src, header, new_data):
        #print "got data from ffmpeg"
        self.vlog2.write(new_data)
        self.rencoded_buffer += new_data

        if self.UNIT not in self.rencoded_buffer:
            return
        usplit = self.rencoded_buffer.split(self.UNIT)
        assert usplit[0] == ''
        self.rencoded_buffer = self.UNIT + usplit[-1]
        for nal_data in usplit[1:-1]:
            #print "nal_dat size", len(nal_data)
            h0 = ord(nal_data[0])
            if h0 & 0x1F == 5:
                #print "skipping iframe"
                #continue #skip iframe
                pass
            elif h0 & 0x1F == 5:
                self.sent_iframe = True
            if len(nal_data) <= self.PS:
                yield self.write_nal_fragment(src, nal_data, header, end=True)
            else:
                #FU-A fragmentation
                fragment_type = 28
                n0 = h0 & 0xE0 | fragment_type
                n1 = h0 & 0x1F
                yield self.write_nal_fragment(src, chr(n0) + chr(0x80 | n1) + nal_data[1:self.PS-1], header, end=False)
                nal_data = nal_data[self.PS-1:]
                while len(nal_data) > self.PS-2:
                    yield self.write_nal_fragment(src, chr(n0) + chr(n1) + nal_data[:self.PS-2], header, end=False)
                    nal_data = nal_data[self.PS-2:]
                yield self.write_nal_fragment(src, chr(n0) + chr(0x40 | n1) + nal_data, header, end=True)

    @gen.coroutine
    def write_nal_fragment(self, src, data, header, end=True):
        dst = self.route(src, header)
        #print "writing nal to dst", len(data)
        mark = 0x80 if end else 0 
        head = struct.pack("!BBHII", 0x80, 96 | mark, self.seq, self.ts, 0)
        self.seq += 1
        self.rlogo.write(repr(head + data) + '\n')
        yield self.write_back(dst, header, head + data)


