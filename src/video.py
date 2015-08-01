from base import NetLayer

from tornado import gen
from tornado.ioloop import IOLoop

import struct
import subprocess
import fcntl
import os
import socket

def binprint(d):
    print " ".join(["{0:02x}".format(ord(c)) for c in d])

def get_script(path):
    return os.path.join(
            os.path.dirname(os.path.realpath(__file__)),
            path)

class FfmpegLayer(NetLayer):
    NAME="ffmpeg"
    COMMANDS = {
        #"negflip": ["/usr/bin/ffmpeg", "-y", "-i",  "pipe:0", "-vf", "negate, vflip", "-f", "h264", "pipe:1"],
        "negflip":  ["/usr/bin/ffmpeg", "-y", "-f", "h264", "-i", "-", "-vf", "negate, vflip", "-f", "h264", "-"],
        "hack":     ["sh", get_script("../misc/haxed.sh")],
        "layer":    ["/usr/bin/ffmpeg", "-y", "-f", "h264", "-i", "-", "-i", "pipe:???", "-filter_complex", """
            [1:v] crop=1/2*in_w:1/2*in_h:1/2*in_w:0 [loop];
            [0:v] [loop] overlay=1/2*main_w:0 [output]""", "-map", "[output]", "-f", "h264", "-"],
        "tee":      ["tee", "out.h264"],
        "cat":      ["cat"]
    }
    UNIT1 = '\x00\x00\x01'
    UNIT2 = '\x00\x00\x00\x01'

    def __init__(self, *args, **kwargs):
        #TODO: This only supports one stream/connection

        ffmpeg_log = kwargs.pop("log", "/tmp/ffmpeg.log")
        cmd_name = kwargs.pop("cmd", "hack")

        super(FfmpegLayer, self).__init__(*args, **kwargs)

        if cmd_name not in self.COMMANDS:
            print "Invalid ffmpeg command name '{}', using cat. (valid: {})".format(cmd_name, " ".join(self.COMMANDS))
            cmd_name = "cat"
        else:
            self.log("ffmpeg using command '{}'".format(cmd_name))


        ffmpeg_log = open(ffmpeg_log, "w")

        self.ioloop = IOLoop.instance()

        pipe_fd = self.make_loop("loop.h264")
        cmd = ["/usr/bin/ffmpeg", "-y", "-f", "h264", "-i", "pipe:{0}".format(pipe_fd), "-i", "-", "-filter_complex", """
            [1:v] crop=1/2*in_w:1/2*in_h:1/2*in_w:0 [loop];
            [0:v] [loop] overlay=1/2*main_w:0 [output]""", "-map", "[output]", "-f", "h264", "-"]
        #self.ffmpeg = subprocess.Popen(self.COMMANDS[cmd_name], stdout=subprocess.PIPE, stdin=subprocess.PIPE, stderr=ffmpeg_log)
        self.ffmpeg = subprocess.Popen(cmd, stdout=subprocess.PIPE, stdin=subprocess.PIPE, stderr=ffmpeg_log)

        fcntl.fcntl(self.ffmpeg.stdout.fileno(), fcntl.F_SETFL, os.O_NONBLOCK)
        fcntl.fcntl(self.ffmpeg.stdin.fileno(), fcntl.F_SETFL, os.O_NONBLOCK)

        self.ioloop.add_handler(self.ffmpeg.stdout.fileno(), self.ffmpeg_read_handler, IOLoop.READ)

        self.frames_skipped = 0

        # FIXME: support multiple streams
        self.last_src = None
        self.last_header = None

        self.prefill_in = 110
        self.ffmpeg_ready = False
        self.incoming_ffmpeg = ""

    def make_loop(self, filename):
        loop = open(filename,"r").read()
        (fifo_read, fifo_write) = os.pipe()
        fcntl.fcntl(fifo_write, fcntl.F_SETFL, os.O_NONBLOCK)

        pos = [0]
        def on_writable(fd, event):
            print "write"
            if event & IOLoop.WRITE:
                n = 0
                n = os.write(fd, loop[pos[0]:]) + pos[0]
                while n == len(loop):
                    n = os.write(fd, loop)
                pos[0] = n

        self.ioloop.add_handler(fifo_write, on_writable, IOLoop.WRITE)

        return fifo_read

    @gen.coroutine
    def on_read(self, src, header, data):
        self.last_src = src
        self.last_header = header

        try:
            self.ffmpeg.stdin.write(data)
            self.ffmpeg.stdin.flush()
        except IOError:
            print "ERROR! FFMPEG is too slow"

        if not self.ffmpeg_ready:
            yield self.passthru(src, header, data)

    def ffmpeg_read_handler(self, fd, events):
        # TODO neaten up this code
        t = self.ffmpeg.stdout.read()
        self.incoming_ffmpeg += t
        self.incoming_ffmpeg = self.incoming_ffmpeg.replace(self.UNIT2, self.UNIT1)

        frames = self.incoming_ffmpeg.split(self.UNIT1)
        assert frames[0] == '' or frames[0] == '\x00'
        self.incoming_ffmpeg = self.UNIT2 + frames[-1]
        for frame in frames[1:-1]:
            if self.prefill_in:
                self.prefill_in -= 1
                continue

            if not self.ffmpeg_ready:
                if ord(frame[0]) & 0x1F == 7:
                    self.ffmpeg_ready = True
                    print "FFMPEG running."
                else:
                    continue

            dst = self.route(self.last_src, self.last_header)
            self.add_future(self.write_back(dst, self.last_header, self.UNIT2 + frame))

    def do_status(self):
        """Print current ffmpeg status"""
        return "{0.prefill_in} {0.ffmpeg_ready}".format(self)

class H264NalLayer(NetLayer):
    # https://tools.ietf.org/html/rfc3984
    NAME = "h264"
    UNIT = "\x00\x00\x01"
    PS = 1396
    TS_INCR = 3600
    DATAMOSH_RATE = 0.1

    def __init__(self, *args, **kwargs):
        super(H264NalLayer, self).__init__(*args, **kwargs)
        self.connections = {}
        self.make_toggle("datamosh")

    #def match(self, src, header):
    #    return self.port is None or header["udp_dport"] == self.port or header["udp_sport"] == self.port

    def get_connection(self, header, incoming):
        conn_id = None
        if incoming:
            if "udp_conn" in header:
                conn_id = header["h264_conn"] = ("UDP", header["udp_conn"])
            elif "tcp_conn" in header:
                conn_id = header["h264_conn"] = ("TCP", header["tcp_conn"])
        else:
            conn_id = header["h264_conn"]

        if conn_id is None:
            return None

        if incoming and (conn_id not in self.connections):
            self.connections[conn_id] = {}

        return self.connections.get(conn_id)

    @gen.coroutine
    def on_read(self, src, header, data):
        # Strip NAL encoding (supporting FU-A fragmentation) 
        # And pass on reconstructed H.264 fragments to the next layer

        conn = self.get_connection(header, incoming=True)
        if conn is None:
            yield self.passthru(src, header, data)
            return
        elif len(conn) == 0:
            conn["seq_num"] = 0
            conn["frag_unit_started"] = False
            conn["rencoded_buffer"] = ''
            conn["fragment_buffer"] = ''
            conn["nal_type_buffer"] = 0
            conn["nal_timestamp"] = None
            conn["time_skew"] = 0

        # Drop packets less than 12 bytes silently
        if len(data) >= 12: #and data[0x2b] == '\xe0':
            hdr, contents = data[:12], data[12:]

            # https://tools.ietf.org/html/rfc3984#section-5.1
            flags, payload_type, seq_num, timestamp, ident = struct.unpack("!BBHII", hdr)
            header["nal_timestamp"] = timestamp
            if conn["nal_timestamp"] is None:
                conn["nal_timestamp"] = timestamp

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
                # https://tools.ietf.org/html/rfc6184#section-5.4
                fragment_type = n0 & 0x1F 

                # Unfragmented
                if fragment_type < 24:
                    header["nal_type"] = n0 & 0x1F
                    h264_fragment = self.UNIT + nal_unit
                    yield self.bubble(src, header, h264_fragment)

                # Fragmented with FU-A
                elif fragment_type == 28:
                    # Start of fragment:
                    if n1 & 0x80:
                        conn["nal_type_buffer"] = n1 & 0x1F
                        conn["fragment_buffer"] = self.UNIT + chr((n0 & 0xE0) | (n1 & 0x1F)) + nal_unit[2:]

                    # End of a fragment
                    #header["nal_type"] = self.nal_type
                    elif n1 & 0x40 and conn["fragment_buffer"] is not None:
                        header["nal_type"] = conn["nal_type_buffer"]
                        conn["fragment_buffer"] += nal_unit[2:] 
                        yield self.bubble(src, header, conn["fragment_buffer"])
                        conn["fragment_buffer"] = None
                        conn["nal_type_buffer"] = None

                    # Middle of a fragment
                    elif conn["fragment_buffer"] is not None:
                        conn["fragment_buffer"] += nal_unit[2:]

                if 'nal_type' in header:
                    conn["time_skew"] = timestamp - conn["nal_timestamp"]

    @gen.coroutine
    def write(self, dst, header, data):
        conn = self.get_connection(header, incoming=False)
        if not conn:
            print "H264: Invalid connection info in header, dropping packet!"
            return

        conn["rencoded_buffer"] += data
        if self.UNIT not in conn["rencoded_buffer"]:
            return

        # TODO also accept 0x00 0x00 0x01 as UNIT
        usplit = map(lambda x: x[1:] if x and x[0] == '\x00' else x, conn["rencoded_buffer"].split(self.UNIT))
        conn["rencoded_buffer"] = self.UNIT + usplit[-1]

        # Assert that there wasn't data before the first H.624 frame
        # Otherwise, drop it with a warning
        if usplit[0] != '':
            print "Warning: received invalid H.264 frame"

        for nal_data in usplit[1:-1]:
            # First byte can be used to determine frame type (I, P, B)
            h0 = ord(nal_data[0])

            # I-frame
            if h0 & 0x1F == 5:
                # Implement datamoshing by skipping IDR's
                if self.datamosh and random.random() > self.DATAMOSH_RATE: 
                    continue

            if h0 & 0x1F in {5, 1}: # IDR's & Coded slices increment timestamp
                conn["nal_timestamp"] += self.TS_INCR

            # TODO:  Re-generate timestamps

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
                nal_data = nal_data[self.PS-1:]

                # Write intermediate datagrams
                while len(nal_data) > self.PS-2:
                    yield self.write_nal_fragment(dst, header, chr(n0) + chr(n1) + nal_data[:self.PS-2], end=False)
                    nal_data = nal_data[self.PS-2:]

                # Write first datagram which has 0x40 set on the second byte
                yield self.write_nal_fragment(dst, header, chr(n0) + chr(0x40 | n1) + nal_data, end=True)

    @gen.coroutine
    def write_nal_fragment(self, dst, header, data, end=True):
        conn = self.get_connection(header, incoming=False)
        payload_type = 96 # H.264
        mark = 0x80 if end else 0 
        #timestamp = header.get("nal_timestamp", 0) & 0xFFFFFFFF # 4 bytes
        timestamp = conn["nal_timestamp"] & 0xFFFFFFFF
        head = struct.pack("!BBHII", 0x80, payload_type | mark, conn["seq_num"], timestamp, 0)
        conn["seq_num"] = (conn["seq_num"] + 1) & 0xFFFF # 2 bytes

        yield self.write_back(dst, header, head + data)

    def do_skew(self):
        """Print the current time skew from the source video (dropped frames)."""
        for conn_id, conn in self.connections.items():
            return "{} - Skew: {} frames".format(conn_id, conn["time_skew"] / 3600)



