from base import NetLayer

from tornado import gen
from tornado.ioloop import IOLoop

import struct
import subprocess
import fcntl
import os

def binprint(d):
    print " ".join(["{0:02x}".format(ord(c)) for c in d])

class FfmpegLayer(NetLayer):
    #TRANSCODE = ["/usr/bin/ffmpeg", "-y", "-i",  "pipe:0", "-vf", "negate, vflip", "-f", "h264", "pipe:1"]
    #TRANSCODE = ["/usr/bin/ffmpeg", "-y", "-f", "h264", "-i", "-", "-vf", "negate, vflip", "-f", "h264", "-"]
    TRANSCODE = ["/usr/bin/sh", "./misc/haxed.sh"]
    #TRANSCODE = ["tee","out.h264"]
    #TRANSCODE = ["cat"]

    def __init__(self, *args, **kwargs):
        super(FfmpegLayer, self).__init__(*args, **kwargs)

        self.ffmpeg = subprocess.Popen(self.TRANSCODE, stdout=subprocess.PIPE, stdin=subprocess.PIPE)
        fcntl.fcntl(self.ffmpeg.stdout.fileno(), fcntl.F_SETFL, os.O_NONBLOCK)
        fcntl.fcntl(self.ffmpeg.stdin.fileno(), fcntl.F_SETFL, os.O_NONBLOCK)
        self.ioloop = IOLoop.instance()
        self.ioloop.add_handler(self.ffmpeg.stdout.fileno(), self.ffmpeg_read_handler, IOLoop.READ)

        self.do_loop = False
        if self.do_loop:
            f = open("/tmp/voutff")
            self.templ = f.read()
            self.ffmpeg.stdin.write(self.templ)
        else:
            self.templ = "xxx"
        self.tp = self.templ
        #self.ffmpeg.stdin.write(self.templ)
        # FIXME: support multiple streams
        self.last_src = None
        self.last_header = None

    @gen.coroutine
    def on_read(self, src, header, data):
        self.last_src = src
        self.last_header = header
        #print "incoming frame."
        if self.do_loop:
            self.ffmpeg.stdin.write(self.tp[:len(nout)])
            self.tp = self.tp[len(nout):]
            if not self.tp:
                self.tp = self.templ
        else:
            try:
                self.ffmpeg.stdin.write(data)
                self.ffmpeg.stdin.flush()
            except IOError:
                print "ERROR! FFMPEG is too slow"

    def ffmpeg_read_handler(self, fd, events):
        new_data = self.ffmpeg.stdout.read()
        #print "outgoing frame"
        if new_data and self.last_src is not None and self.last_header is not None:
            dst = self.route(self.last_src, self.last_header)
            f = self.write_back(dst, self.last_header, new_data)
            if f:
                self.ioloop.add_future(f, lambda f: None)

class H264NalLayer(NetLayer):
    SINGLE_CHILD = True
    UNIT = "\x00\x00\x00\x01"
    PS = 1396

    def __init__(self, *args, **kwargs):
        log_prefix = kwargs.pop('log_prefix', None)
        self.passthrough = kwargs.pop("passthrough", False)

        super(H264NalLayer, self).__init__(*args, **kwargs)
        
        if log_prefix is not None:
            self.log_raw = open(log_prefix + ".raw", 'w')
            self.log_input = open(log_prefix + ".input", 'w')
            self.log_output = open(log_prefix + ".output", 'w')
        else:
            self.log_raw = None
            self.log_input = None
            self.log_output = None

        self.vlog = open('/tmp/vout', 'w')
        self.vlog2 = open('/tmp/vout2', 'w')
        self.rlogi = open('/tmp/rlogi', 'w')
        self.rlogo = open('/tmp/rlogo', 'w')

        self.seq = 0
        self.ts = 0
        self.fu_start = False
        self.rencoded_buffer = ''
        self.sent_iframe = False

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
                #print 'match', seq, ts, ident, flags, len(d)
                nalu = d
                n0 = ord(nalu[0])
                n1 = ord(nalu[1])
                fragment_type = n0 & 0x1F
                if fragment_type < 24: # unfragmented
                    self.nout = self.UNIT + nalu
                    #self.got_frame(self.nout)
                    yield self.bubble(src, header, self.nout)
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
                                #self.got_frame(self.nout)
                                yield self.bubble(src, header, self.nout)
                                if self.log_input is not None:
                                    self.log_input.write(self.nout)
                                    self.log_input.flush()
                        else:
                            print "skipping packet :("

                #yield self.pass_on(src, header)
                #yield self.passthru(src, data, header)


    @gen.coroutine
    def write(self, dst, header, data):
        #print "got data from ffmpeg"
        self.rencoded_buffer += data

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
                yield self.write_nal_fragment(dst, header, nal_data, end=True)
            else:
                #FU-A fragmentation
                fragment_type = 28
                n0 = h0 & 0xE0 | fragment_type
                n1 = h0 & 0x1F
                yield self.write_nal_fragment(dst, header, chr(n0) + chr(0x80 | n1) + nal_data[1:self.PS-1], end=False)
                nal_data = nal_data[self.PS-1:]
                while len(nal_data) > self.PS-2:
                    yield self.write_nal_fragment(dst, header, chr(n0) + chr(n1) + nal_data[:self.PS-2], end=False)
                    nal_data = nal_data[self.PS-2:]
                yield self.write_nal_fragment(dst, header, chr(n0) + chr(0x40 | n1) + nal_data, end=True)

    @gen.coroutine
    def write_nal_fragment(self, dst, header, data, end=True):
        print "writing nal to dst", len(data)
        mark = 0x80 if end else 0 
        head = struct.pack("!BBHII", 0x80, 96 | mark, self.seq, self.ts, 0)
        self.seq += 1
        self.rlogo.write(repr(head + data) + '\n')
        yield self.write_back(dst, header, head + data)


