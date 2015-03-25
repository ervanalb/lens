from ethernet import NetLayer

import dpkt 

class UDPLayer(ethernet.NetLayer):
    IN_TYPES = "IP"
    OUT_TYPE = "UDP"

    def __init__(self, prev_layer=None):
        self.prev_layer = prev_layer
        self.apps = {}

    def register_app(self, port, handler):
        self.apps[port] = handler

    @gen.coroutine
    def on_read(self, src, data):

    @gen.coroutine
    def write_udp(self, dst, data):

