#!/usr/bin/python2
import dpkt
import driver
import enum
import ethernet 
import tcp

import tornado.gen as gen

class IPv4Layer(ethernet.NetLayer):
    @staticmethod
    def pretty_ip(ip):
        return ".".join([str(ord(x)) for x in ip])

    def __init__(self, prev_layer=None, next_layer=None, addr_filter=None):
        self.prev_layer = prev_layer
        self.next_layer = next_layer
        self.addr_filter = addr_filter

    @gen.coroutine
    def on_read(self, src, data):
        pkt = dpkt.ethernet.Ethernet(data)
        if pkt.type == dpkt.ethernet.ETH_TYPE_IP:
            if self.addr_filter is None or self.pretty_ip(pkt.data.src) in self.addr_filter or self.pretty_ip(pkt.data.dst) in self.addr_filter:
                #print src, repr(pkt)
                yield self.bubble(src, data)
            return 
        yield self.write(self.route(src), data)
        
class TCPPassthruLayer(ethernet.NetLayer):
    def __init__(self, prev_layer=None, next_layer=None, ports=None):
        self.prev_layer = prev_layer
        self.next_layer = next_layer
        self.ports = ports

    @gen.coroutine
    def on_read(self, src, data):
        pkt = dpkt.ethernet.Ethernet(data)
        if pkt.type == dpkt.ethernet.ETH_TYPE_IP:
            if pkt.data.p == dpkt.ip.IP_PROTO_TCP:
                if pkt.data.data.sport in self.ports or pkt.data.data.dport in self.ports:
                    yield self.write(self.route(src), data)
                    return
        yield self.bubble(src, data)

class LineBufferLayer(tcp.TCPApplicationLayer):
    # Buffers incoming data line-by-line
    def __init__(self, *args, **kwargs):
        super(LineBufferLayer, self).__init__(*args, **kwargs)
        self.buff = ""
        
    @gen.coroutine
    def on_read(self, src, data):
        if data is None:
            buff = self.buff
            self.buff = ""
            yield self.bubble(src, buff)
        else:
            self.buff += data
            if '\n' in self.buff:
                lines = self.buff.split('\n')
                print 'linebuffer: %d newlines' % (len(lines) -1)
                self.buff = lines[-1]
                for line in lines[:-1]:
                    yield self.bubble(src, line + "\n")
            else:
                print 'linebuffer: no newline'

    @gen.coroutine
    def on_close(self, src):
        if self.buff:
            yield self.bubble(src, self.buff)
        yield super(LineBufferLayer, self).on_close(src)

class CloudToButtLayer(tcp.TCPApplicationLayer):
    @gen.coroutine
    def on_read(self, src, data):
        print 'cloud2butt: replacing in %d bytes' % len(data)
        butt_data = data.replace("cloud", "butt")
        yield self.bubble(src, butt_data)

def connect(prev, layer_list, **global_kwargs):
    layers = []
    for (const, args, kwargs) in layer_list:
        kwargs.update(global_kwargs)
        new = const(*args, prev_layer=prev, **kwargs)
        layers.append(new)
        prev.next_layer = new
        prev = new
    return layers

# Simple syntatic sugar
def l(constructor, *args, **kwargs):
    return (constructor, args, kwargs)

if __name__ == "__main__":
    addr = "18.238.0.97"
    print "Capturing traffic to:", addr

    tap = driver.Tap()

    loop, link_layer = ethernet.build_ethernet_loop()
    tap.mitm()

    stateless_layers = connect(
        link_layer, [
        l(IPv4Layer, addr_filter=[addr]),
        l(TCPPassthruLayer, ports=[22]),
        l(tcp.TCPLayer),
    ])

    def stateful_layers(conn, prev_layer):
        layers = connect(
            prev_layer, [
            l(LineBufferLayer),
            l(CloudToButtLayer), 
        ], conn=conn)
        # Fix prev_layer.next_layer munging
        prev_layer.next_layer = stateful_layers 
        return layers[0]

    stateless_layers[-1].next_layer = stateful_layers

    try:
        loop.start()
    except:
        tap.passthru()

