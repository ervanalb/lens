#!/usr/bin/python2
import dpkt
import driver
import enum

import ethernet 
import ip
import tcp
import udp
import http


import tornado.gen as gen

class LineBufferLayer(ethernet.NetLayer):
    IN_TYPES = {"TCP App"}
    OUT_TYPE = "TCP App"
    # Buffers incoming data line-by-line
    def __init__(self, *args, **kwargs):
        super(LineBufferLayer, self).__init__(*args, **kwargs)
        self.buff = ""
        
    @gen.coroutine
    def on_read(self, src, data, *args):
        if data is None:
            buff = self.buff
            self.buff = ""
            yield self.bubble(src, buff, *args)
        else:
            self.buff += data
            if '\n' in self.buff:
                lines = self.buff.split('\n')
                #print 'linebuffer: %d newlines' % (len(lines) -1)
                self.buff = lines[-1]
                for line in lines[:-1]:
                    yield self.bubble(src, line + "\n", *args)
            else:
                #print 'linebuffer: no newline'
                pass

    @gen.coroutine
    def on_close(self, src, conn):
        if self.buff:
            yield self.bubble(src, self.buff)
        #yield super(LineBufferLayer, self).on_close(src, conn)

class CloudToButtLayer(ethernet.NetLayer):
    IN_TYPES = {"TCP App"}
    OUT_TYPE = "TCP App"
    @gen.coroutine
    def on_read(self, src, data, *args):
        #print 'cloud2butt: replacing in %d bytes' % len(data)
        butt_data = data.replace("nginx", "my butt")
        yield self.bubble(src, butt_data, *args)

def connect(prev, layer_list, **global_kwargs):
    layers = []
    for (const, args, kwargs) in layer_list:
        kwargs.update(global_kwargs)
        new = const(*args, prev_layer=prev, **kwargs)
        layers.append(new)
        if prev.OUT_TYPE not in new.IN_TYPES:
            print "Warning: connecting incompatible {} -> {}".format(repr(prev), repr(new))
        prev.next_layer = new
        prev = new
    return layers

# Simple syntatic sugar
def l(constructor, *args, **kwargs):
    return (constructor, args, kwargs)

if __name__ == "__main__":
    #addr = "18.238.0.97"
    addr = "192.168.1.10"
    print "Capturing traffic to:", addr

    tap = driver.Tap()

    loop, link_layer = ethernet.build_ethernet_loop()
    tap.mitm()

    stateless_layers = connect(
        link_layer, [
        l(ethernet.EthernetLayer),
        l(ip.IPv4Layer, addr_filter=[addr]),
        l(udp.UDPLayer),
        l(tcp.TCPPassthruLayer, ports=[22]),
        l(tcp.TCPLayer, debug=False),
    ])
    udp_layer = stateless_layers[2]
    tcp_layer = stateless_layers[-1]

    def stateful_layers(prev_layer, *args, **kwargs):
        try:
            layers = connect(
                prev_layer, [
                l(LineBufferLayer),
                #l(CloudToButtLayer, *args, **kwargs), 
                l(http.HTTPLayer, *args, **kwargs),
            ])
        except:
            prev_layer.next_layer = stateful_layers 
            raise
        # Fix prev_layer.next_layer munging
        prev_layer.next_layer = stateful_layers 
        print prev_layer.next_layer, 'state'
        return layers[0]

    tcp_layer.next_layer = stateful_layers
    udp_layer.register_app(udp.UDPVideoLayer)

    try:
        loop.start()
    except:
        tap.passthru()

