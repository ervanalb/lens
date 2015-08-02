from base import NetLayer, gen
from tornado import gen, httputil
from util import MultiOrderedDict

class RTSPLayer(NetLayer):
    NAME = "rtsp"
    CONN_ID_KEY = "tcp_conn"

    def __init__(self, *args, **kwargs):
        super(RTSPLayer, self).__init__(*args, **kwargs)
        self.connections = {}

    @gen.coroutine
    def on_read(self, src, conn, data):
        conn_id = conn[self.CONN_ID_KEY]
        if conn_id not in self.connections:
            dst = self.route(src, conn)
            req = self.request(conn, dst, src)
            req.next()
            resp = self.response(conn, src, dst)
            resp.next()
            self.connections[conn_id] = {src: req, dst: resp}

        if src in {0, 1}:
            self.connections[conn_id][src].send(data)
        else:
            self.log("Unknown src: {}", src)
            yield self.passthru(src, conn, data)

    def parse_header_line(self, hdict, line):
        if line[0].isspace():
            # continuation of a multi-line header
            new_part = ' ' + line.lstrip()
            hdict.last_value_append(new_part)
        else:
            name, value = line.split(":", 1)
            hdict.push(name, value.strip())

    def request(self, conn, src, dst):
        keep_alive = True
        req = None
        conn = conn.copy()

        req_line = yield 
        while keep_alive and req_line is not None:
            body = ""
            headers = MultiOrderedDict()
            try:
                req = httputil.RequestStartLine(*req_line.split())
            except ValueError:
                if req_line != "":
                    self.log("Error: Malformed request start line: '{}'", req_line)
                req_line = yield
                continue
            while True:
                header_line = yield
                if header_line is None:
                    break
                if not header_line.strip():
                    break
                self.parse_header_line(headers, header_line.strip())

            if req.version != "RTSP/1.0":
                self.log("Unknown version! '{}'", req.version)

            if "content-length" in headers:
                try:
                    content_length = int(headers.last("content-length"))
                except ValueError:
                    content_length = None
                    self.log("Warning: invalid content length '{}'", headers.last('content-length'))
            else:
                content_length = 0
            
            if header_line is not None:
                conn["lbl_disable"](dst)
                while len(body) < content_length or content_length is None:
                    data = yield
                    if data is None:
                        break
                    body += data

            if "content-encoding" in headers:
                encoding = headers.last("content-encoding")
                if encoding in self.ENCODERS:
                    body = self.ENCODERS[encoding](body)

            conn["lbl_enable"](dst)
            conn["rtsp_headers"] = headers
            conn["rtsp_request"] = req
            req_line = yield self.bubble(dst, conn, body)

    def response(self, conn, src, dst):
        keep_alive = True
        resp = None
        conn = conn.copy()

        start_line = yield 
        while keep_alive and start_line is not None:
            body = ""
            headers = MultiOrderedDict()
            try:
                resp = httputil.ResponseStartLine(*start_line.split())
            except ValueError:
                if start_line != "":
                    self.log("Error: Malformed response start line: '{}'", start_line)
                start_line = yield
                continue
            while True:
                header_line = yield
                if header_line is None:
                    self.log("Warning: Terminated early?")
                    return
                if not header_line.strip():
                    break
                self.parse_header_line(headers, header_line.strip())

            if resp.version != "RTSP/1.0":
                self.log("Unknown version! '{}'", resp.version)

            if "content-length" in headers:
                try:
                    content_length = int(headers.last("content-length"))
                except ValueError:
                    content_length = None
                    self.log("Warning: invalid content length '{}'", headers.last('content-length'))
            else:
                content_length = 0


            if header_line is not None:
                conn["lbl_disable"](dst)
                while len(body) < content_length or content_length is None:
                    data = yield
                    if data is None:
                        break
                    body += data

            if "content-encoding" in headers:
                encoding = headers.last("content-encoding")
                if encoding in self.ENCODERS:
                    body = self.ENCODERS[encoding](body)

            conn["lbl_enable"](dst)
            conn["rtsp_headers"] = headers
            conn["rtsp_response"] = resp
            start_line = yield self.bubble(dst, conn, body)

    @gen.coroutine
    def on_close(self, src, conn):
        conn_id = conn[self.CONN_ID_KEY]
        if conn_id in self.connections and src in {0, 1}:
            self.connections[conn_id][src].send(None)
        yield self.close_bubble(src, conn)

    @gen.coroutine
    def write(self, dst, conn, data):
        if "rtsp_request" in conn:
            start_line = "{0.method} {0.path} {0.version}\r\n".format(conn["rtsp_request"])
        elif "rtsp_response" in conn:
            start_line = "{0.version} {0.code} {0.reason}\r\n".format(conn["rtsp_response"])
        else:
            raise Exception("No start line for HTTP")

        output = start_line
        #yield self.write_back(dst, conn, start_line)

        headers = conn["rtsp_headers"]
        if "content-length" in headers:
            headers.set("Content-Length", str(len(data)))
        if "content-encoding" in headers:
            encoding = headers.last("content-encoding")
            if encoding in self.ENCODERS:
                data = self.ENCODERS[encoding](data)

        for key, value in headers:
            multiline_value = value.replace("\n", "\n ")
            line = "{}: {}\r\n".format(key, multiline_value)
            output += line
            #yield self.write_back(dst, conn, line)

        self.log(">> {}", output)

        #yield self.write_back(dst, conn, "\r\n")
        #yield self.write_back(dst, conn, data)

        output += "\r\n"
        output += data
        yield self.write_back(dst, conn, output)
        #yield self.write_back(dst, conn, None)
