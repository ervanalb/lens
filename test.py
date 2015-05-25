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
    def on_read(self, src):
        while True:
            n = random.randint(400, 1200)
            data = self.in_files[src].read(n)
            yield self.bubble(src, data, {})
            if len(data) < n:
                yield self.on_close(src)
                break

    @gen.coroutine
    def write(self, dst, payload, header):
        self.out_files[dst].write(payload)

if __name__ == "__main__":
    import sys
    import logging

    logging.basicConfig()

    BASE_NAME = "tests/basic.http.%d"
    in_files = {x: open(BASE_NAME % x) for x in [0, 1]}
    out_files = {x: open((BASE_NAME % x) + ".out", "w") for x in [0, 1]}

    file_layer = FileTestLayer(in_files, out_files)

    layers = connect(
            file_layer, [
            l(base.LineBufferLayer),
            l(http.HTTPLayer, 0, 1),
            l(base.CloudToButtLayer)
        ])

    file_layer.on_read(0)
    file_layer.on_read(1)

