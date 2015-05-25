import zlib

from base import NetLayer, MultiOrderedDict
from tornado import gen, httputil


#class HTTPLayer(TCPApplicationLayer):
class HTTPLayer(NetLayer):
    IN_TYPES = {"TCP App"}
    OUT_TYPE = "HTTP"

    SINGLE_CHILD = False

    ENCODERS = {
        "gzip": zlib.compress,
    }

    DECODERS = {
        "gzip": zlib.decompress,
    }

    CONN_ID_KEY = "tcp_conn"

    def __init__(self, *args, **kwargs):
        super(HTTPLayer, self).__init__(*args, **kwargs)
        self.connections = {}

    def match_child(self, src, header, key):
        #TODO
        return True

    @gen.coroutine
    def on_read(self, src, conn, data):
        conn_id = conn[self.CONN_ID_KEY]
        if conn_id not in self.connections:
            req = self.request(conn)
            req.next()
            resp = self.response(conn)
            resp.next()
            self.connections[conn_id] = (req, resp)
        
        if src in {0, 1}:
            self.connections[conn_id][src].send(data)
        else:
            print "Unknown src: {}"
            yield self.passthru(src, data, conn)
        #yield self.bubble(src, data, conn)


    def parse_header_line(self, hdict, line):
        if line[0].isspace():
            # continuation of a multi-line header
            new_part = ' ' + line.lstrip()
            hdict.last_value_append(new_part)
        else:
            name, value = line.split(":", 1)
            hdict.push(name, value.strip())

    def request(self, conn):
        keep_alive = True
        req = None
        headers = MultiOrderedDict()
        body = ""
        conn = conn.copy()

        @gen.coroutine
        def bubble(data):
            conn["http_headers"] = headers
            conn["http_request"] = req
            yield self.bubble(0, conn, data)

        while keep_alive:
            req_line = yield 
            req = httputil.parse_request_start_line(req_line.strip())
            while True:
                header_line = yield
                if header_line is None:
                    break
                if not header_line.strip():
                    break
                self.parse_header_line(headers, header_line.strip())

            if req.version == "HTTP/1.0":
                keep_alive = headers.last("connection", "").lower().strip() == "keep-alive"
            else:
                keep_alive = headers.last("connection", "").lower().strip() != "close"

            if "content-length" in headers:
                try:
                    content_length = int(headers.last("content-length"))
                except ValueError:
                    content_length = None
            else:
                content_length = None

            if req.method != "POST":
                content_length = content_length or 0

            
            if header_line is not None:
                while len(body) < content_length or content_length is None:
                    data = yield
                    if data is None:
                        break
                    body += data

            if "content-encoding" in headers:
                encoding = headers.last("content-encoding")
                if encoding in self.ENCODERS:
                    body = self.ENCODERS[encoding](body)

            yield bubble(body)
            break

    def response(self, conn):
        keep_alive = True
        resp = None
        headers = MultiOrderedDict()
        body = ""
        conn = conn.copy()

        @gen.coroutine
        def bubble(data):
            conn["http_headers"] = headers
            conn["http_response"] = resp
            yield self.bubble(1, conn, data)

        while keep_alive:
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

            if resp.version == "HTTP/1.0":
                keep_alive = headers.last("connection", "").lower().strip() == "keep-alive"
            else:
                keep_alive = headers.last("connection", "").lower().strip() != "close"

            if "content-length" in headers:
                try:
                    content_length = int(headers.last("content-length"))
                except ValueError:
                    content_length = None
            else:
                content_length = None


            if header_line is not None:
                while len(body) < content_length or content_length is None:
                    data = yield
                    if data is None:
                        break
                    body += data

            if "content-encoding" in headers:
                encoding = headers.last("content-encoding")
                if encoding in self.ENCODERS:
                    body = self.ENCODERS[encoding](body)

            yield bubble(body)
            break

    @gen.coroutine
    def on_close(self, src, conn):
        conn_id = conn[self.CONN_ID_KEY]
        if conn_id in self.connections and src in {0, 1}:
            self.connections[conn_id][src].send(None)
        yield self.close_bubble(src, conn)

    @gen.coroutine
    def write(self, dst, conn, data):
        if "http_request" in conn:
            start_line = "{0.method} {0.path} {0.version}\r\n".format(conn["http_request"])
        elif "http_response" in conn:
            start_line = "{0.version} {0.code} {0.reason}\r\n".format(conn["http_response"])
        else:
            raise Exception("No start line for HTTP")

        yield self.write_back(dst, conn, start_line)

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
            yield self.write_back(dst, conn, line)

        yield self.write_back(dst, conn, "\r\n")
        yield self.write_back(dst, conn, data)
