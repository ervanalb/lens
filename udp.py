from ethernet import NetLayer

import dpkt 

class UDPLayer(ethernet.NetLayer):
    IN_TYPES = "IP"
    OUT_TYPE = "UDP"
    def register_app(

    @gen.coroutine
    def on_read(self, src, data):

    @gen.coroutine
    def write_udp(self, dst, data):

