import tornado.gen as gen

class NetLayer(object):
    routing = {
        1: 0,
        0: 1
    }
    # IN_TYPES & OUT_TYPES are used for static type checking so that
    # warnings can be raised when mismatched layers are connected.
    IN_TYPES = set()
    OUT_TYPE = None

    def __init__(self, prev_layer=None, next_layer=None):
        self.prev_layer = prev_layer
        self.next_layer = next_layer

    @gen.coroutine
    def on_read(self, src, payload, header=None):
        yield self.bubble(*args **kwargs)

    @gen.coroutine
    def on_close(self, src, header=None):
        if self.next_layer is not None:
            yield self.next_layer.on_close(src, header)

    @gen.coroutine
    def bubble(self, src, *args, **kwargs):
        # Bubble tries to pass on a message in the following way:
        # 1. If the next layer exists, pass the message to the next layer
        ##XXX# 2. Otherwise, if the previous layer exists, pass the message back
        # 3. Otherwise, use self.write(...), (which probably just writes back to previous layer)
        if self.next_layer is not None:
            yield self.next_layer.on_read(src, *args, **kwargs)
        #XXX This may have broken things, but now it makes sense
        #elif self.prev_layer is not None:
        #    yield self.prev_layer.write(self.route(src), *args, **kwargs)
        else:
            yield self.write(self.route(src), *args, **kwargs)

    @gen.coroutine
    def passthru(self, src, *args, **kwargs):
        # Pass the message through this layer transparently, not bubbling up.
        if self.prev_layer is not None:
            yield self.prev_layer.write(self.route(src), *args, **kwargs)

    @gen.coroutine
    def write(self, dst, payload, header=None):
        # Override me - How does this layer handle messages?
        if self.prev_layer is not None:
            yield self.prev_layer.write(dst, payload, header)

    def route(self, key, header=None):
        # Given a message from port `key`, determine which port to send it to
        return self.routing[key]

    def unroute(self, key, header=None):
        # Given a message to port `key`, determine which port it should have come from
        return self.routing[key]

class LineBufferLayer(NetLayer):
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

class CloudToButtLayer(NetLayer):
    IN_TYPES = {"TCP App"}
    OUT_TYPE = "TCP App"
    @gen.coroutine
    def on_read(self, src, data, *args):
        #print 'cloud2butt: replacing in %d bytes' % len(data)
        butt_data = data.replace("cloud", "my butt")
        yield self.bubble(src, butt_data, *args)


def connect(prev, layer_list, check_types=False, **global_kwargs):
    layers = []
    for (const, args, kwargs) in layer_list:
        kwargs.update(global_kwargs)
        new = const(*args, prev_layer=prev, **kwargs)
        layers.append(new)
        if prev.OUT_TYPE not in new.IN_TYPES and check_types:
            print "Warning: connecting incompatible {} -> {}".format(repr(prev), repr(new))
        prev.next_layer = new
        prev = new
    return layers

# Simple syntatic sugar
def l(constructor, *args, **kwargs):
    return (constructor, args, kwargs)

