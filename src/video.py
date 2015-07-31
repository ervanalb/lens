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

        #ffmpeg_log = open("/dev/null", "w")
        ffmpeg_log = open("/tmp/lens-ffmpeg.log", "w")
        self.ffmpeg = subprocess.Popen(self.TRANSCODE, stdout=subprocess.PIPE, stdin=subprocess.PIPE, stderr=ffmpeg_log)
        fcntl.fcntl(self.ffmpeg.stdout.fileno(), fcntl.F_SETFL, os.O_NONBLOCK)
        fcntl.fcntl(self.ffmpeg.stdin.fileno(), fcntl.F_SETFL, os.O_NONBLOCK)
        self.ioloop = IOLoop.instance()
        self.ioloop.add_handler(self.ffmpeg.stdout.fileno(), self.ffmpeg_read_handler, IOLoop.READ)

        self.do_loop = False
        if self.do_loop:
            f = open("/tmp/lens-ffmpeg-source.h264")
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
        print "incoming frame."
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
        print "outgoing frame"
        if new_data and self.last_src is not None and self.last_header is not None:
            dst = self.route(self.last_src, self.last_header)
            f = self.write_back(dst, self.last_header, new_data)
            if f:
                self.ioloop.add_future(f, lambda f: None)

class H264NalLayer(NetLayer):
    # https://tools.ietf.org/html/rfc3984
    SINGLE_CHILD = True
    UNIT = "\x00\x00\x00\x01"
    PS = 1396

    def __init__(self, *args, **kwargs):
        super(H264NalLayer, self).__init__(*args, **kwargs)
        self.seq_num = 0
        self.timestamp = 0
        self.frag_unit_started = False
        self.rencoded_buffer = ''
        self.sent_iframe = False
        self.fragment_buffer = ''

    @gen.coroutine
    def on_read(self, src, header, data):
        # Drop packets less than 12 bytes silently
        if len(data) >= 12: #and data[0x2b] == '\xe0':
            hdr, contents = data[:12], data[12:]

            # https://tools.ietf.org/html/rfc3984#section-5.1
            flags, payload_type, seq_num, timestamp, ident = struct.unpack("!BBHII", hdr)
            self.timestamp = timestamp

            # The 8th bit of payload_type is the 'marker bit' flag
            # Move it to the 9th bit of `flags` & remove from `payload_type`
            flags |= (payload_type & 0x80) << 1
            payload_type &= 0x7F

            if payload_type == 96: # H.264 only supported right now
                nal_unit = contents
                n0 = ord(nal_unit[0])
                n1 = ord(nal_unit[1])

                # The first 5 bits of the contents are the 'fragment type'
                # Currently only FU-A and unfragmented are supported.
                fragment_type = n0 & 0x1F 
                if fragment_type < 24: # unfragmented
                    h264_fragment = self.UNIT + nal_unit
                    yield self.bubble(src, header, h264_fragment)
                elif fragment_type == 28: # FU-A
                    if n1 & 0x80: # Start of fragment
                        self.fragment_buffer = self.UNIT + chr((n0 & 0xE0) | (n1 & 0x1F)) + nal_unit[2:]
                    elif n1 & 0x40 and self.fragment_buffer is not None: # End of a fragment
                            yield self.bubble(src, header, self.fragment_buffer)
                            self.fragment_buffer = None
                    elif self.fragment_buffer is not None: # Middle of a fragmetn
                        if self.fragment_buffer is not None:
                            self.fragment_buffer += nal_unit[2:]


    @gen.coroutine
    def write(self, dst, header, data):
        self.rencoded_buffer += data
        if self.UNIT not in self.rencoded_buffer:
            return

        usplit = self.rencoded_buffer.split(self.UNIT)
        assert usplit[0] == ''
        self.rencoded_buffer = self.UNIT + usplit[-1]

        for nal_data in usplit[1:-1]:
            # First byte can be used to determine frame type (I, P, B)
            h0 = ord(nal_data[0])
            if h0 & 0x1F == 5: # I-frame
                self.sent_iframe = True

            # Can we fit it the whole frame in 1 packet, or do we need to fragment?
            if len(nal_data) <= self.PS:
                yield self.write_nal_fragment(dst, header, nal_data, end=True)
            else:
                # FU-A fragmentation
                fragment_type = 28

                # Write first datagram which has 0x80 set on the second byte
                n0 = h0 & 0xE0 | fragment_type
                n1 = h0 & 0x1F
                yield self.write_nal_fragment(dst, header, chr(n0) + chr(0x80 | n1) + nal_data[1:self.PS-1], end=False)

                # Write intermediate datagrams
                nal_data = nal_data[self.PS-1:]
                while len(nal_data) > self.PS-2:
                    yield self.write_nal_fragment(dst, header, chr(n0) + chr(n1) + nal_data[:self.PS-2], end=False)
                    nal_data = nal_data[self.PS-2:]

                # Write first datagram which has 0x40 set on the second byte
                yield self.write_nal_fragment(dst, header, chr(n0) + chr(0x40 | n1) + nal_data, end=True)

    @gen.coroutine
    def write_nal_fragment(self, dst, header, data, end=True):
        payload_type = 96 # H.264
        mark = 0x80 if end else 0 
        head = struct.pack("!BBHII", 0x80, payload_type | mark, self.seq_num, self.timestamp, 0)
        self.seq_num += 1
        yield self.write_back(dst, header, head + data)


