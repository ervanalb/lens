import zlib

from base import NetLayer, MultiOrderedDict
from tornado import gen, httputil


#class HTTPLayer(TCPApplicationLayer):
class HTTPLayer(NetLayer):
    IN_TYPES = {"TCP App"}
    OUT_TYPE = "HTTP"
    STATE_START = "start"
    STATE_HEADERS = "headers"

    ENCODERS = {
        "gzip": zlib.compress,
    }

    DECODERS = {
        "gzip": zlib.decompress,
    }

    def __init__(self, sender, reciever, *args, **kwargs):
        super(HTTPLayer, self).__init__(*args, **kwargs)
        self.cl_state = self.STATE_START
        self.sv_state = self.STATE_START
        self.client = sender
        self.server = reciever
        self.client_conn = None
        self.server_conn = None

        self.req = self.request()
        self.req.next()

        self.resp = self.response()
        self.resp.next()

    @gen.coroutine
    def on_read(self, src, data, conn):
        if src == self.client:
            # Client -> Server
            self.client_conn = conn
            self.req.send(data)
        elif src == self.server:
            self.server_conn = conn
            self.resp.send(data)
        else:
            print "Unknown src: {}; ({} -> {})".format(src, self.client, self.server)
        #yield self.bubble(src, data, conn)


    def parse_header_line(self, hdict, line):
        if line[0].isspace():
            # continuation of a multi-line header
            new_part = ' ' + line.lstrip()
            hdict.last_value_append(new_part)
        else:
            name, value = line.split(":", 1)
            hdict.push(name, value.strip())

    def request(self):
        req = None
        headers = MultiOrderedDict()
        body = ""

        @gen.coroutine
        def bubble(data):
            conn = self.client_conn.copy()
            conn["http_headers"] = headers
            conn["http_request"] = req
            yield self.bubble(self.client, data, conn)

        req_line = yield 
        req = httputil.parse_request_start_line(req_line.strip())
        while True:
            header_line = yield
            if header_line is None:
                break
            if not header_line.strip():
                break
            self.parse_header_line(headers, header_line.strip())
        print "REQUEST", req, headers
        if header_line is not None:
            while True:
                data = yield
                if data is None:
                    break
                body += data

        if "content-encoding" in headers:
            encoding = headers.last("content-encoding")
            if encoding in self.ENCODERS:
                body = self.ENCODERS[encoding](body)

        print "REQ BODY ", body
        yield bubble(body)

    def response(self):
        resp = None
        headers = MultiOrderedDict()
        body = ""

        @gen.coroutine
        def bubble(data):
            conn = self.server_conn.copy()
            conn["http_headers"] = headers
            conn["http_response"] = resp
            yield self.bubble(self.server, data, conn)

        start_line = yield 
        resp = httputil.parse_response_start_line(start_line.strip())
        while True:
            header_line = yield
            if header_line is None:
                print "Terminated early?"
                return
            if not header_line.strip():
                break
            self.parse_header_line(headers, header_line.strip())
        print "RESPONSE", resp, headers
        if header_line is not None:
            while True:
                data = yield
                if data is None:
                    break
                body += data

        if "content-encoding" in headers:
            encoding = headers.last("content-encoding")
            if encoding in self.ENCODERS:
                body = self.ENCODERS[encoding](body)

        print "RESP BODY", body
        yield bubble(body)

    @gen.coroutine
    def on_close(self, src, conn):
        if src == self.client:
            self.req.send(None)
        elif src == self.server:
            self.resp.send(None)
        yield super(HTTPLayer, self).on_close(src)

    @gen.coroutine
    def write(self, dst, data, conn):
        if "http_request" in conn:
            start_line = "{0.method} {0.path} {0.version}\r\n".format(conn["http_request"])
        elif "http_response" in conn:
            start_line = "{0.version} {0.code} {0.reason}\r\n".format(conn["http_response"])
        else:
            raise Exception("No start line for HTTP")

        yield self.prev_layer.write(dst, start_line, conn)

        headers = conn["http_headers"]
        if "content-length" in headers:
            headers.set("Content-Length", str(len(data)))
        if "content-encoding" in headers:
            encoding = headers.last("content-encoding")
            if encoding in self.ENCODERS:
                data = self.ENCODERS[encoding](data)

        for key, value in headers:
            multiline_value = value.replace("\n", "\n ")
            line = "{}: {}\r\n".format(key, multiline_value)
            yield self.prev_layer.write(dst, line, conn)

        yield self.prev_layer.write(dst, "\r\n", conn)
        yield self.prev_layer.write(dst, data, conn)
