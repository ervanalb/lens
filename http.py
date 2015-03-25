from tcp import TCPApplicationLayer
from ethernet import NetLayer

#class HTTPLayer(TCPApplicationLayer):
class HTTPLayer(NetLayer):
    IN_TYPES = {"TCP App"}
    OUT_TYPE = "HTTP"
    def __init__(self, *args, **kwargs):
        super(HTTPLayer, self).__init__(*args, **kwargs)

    @gen.coroutine
    def on_read(self, src, data, conn):
        yield self.bubble(src, data)

    @gen.coroutine
    def on_close(self, src, conn):
        yield super(HTTPLayer, self).on_close(src)


