import random
import tornado.gen as gen

import base
import http

from base import l, connect

class FileTestLayer(base.NetLayer):
    def __init__(self, in_files, out_files, *args, **kwargs):
        super(FileTestLayer, self).__init__(*args, **kwargs)
        self.in_files = in_files
        self.out_files = out_files

    @gen.coroutine
    def on_read(self, src, header, data):
        header = {'id': 0}
        while True:
            n = random.randint(400, 1200)
            data = self.in_files[src].read(n)
            yield self.bubble(src, header, data)
            if len(data) < n:
                yield self.close_bubble(src, header)
                break

    @gen.coroutine
    def write(self, dst, header, payload):
        self.out_files[dst].write(payload)

if __name__ == "__main__":
    import sys
    import logging

    logging.basicConfig()

    BASE_NAME = "../tests/basic.http.%d"
    in_files = {x: open(BASE_NAME % x) for x in [0, 1]}
    out_files = {x: open((BASE_NAME % x) + ".out", "w") for x in [0, 1]}

    file_layer = FileTestLayer(in_files, out_files)
    http_lbf_layer = base.LineBufferLayer()
    file_layer.register_child(http_lbf_layer)

    http_layer = http.HTTPLayer()
    http_layer.CONN_ID_KEY = "id"
    http_lbf_layer.register_child(http_layer)

    c2b_layer = base.CloudToButtLayer()
    http_layer.register_child(c2b_layer, "text")

    file_layer.on_read(1, None, None)
    file_layer.on_read(0, None, None)

