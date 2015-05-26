import tornado.gen as gen
import subprocess

class NetLayer(object):
    routing = {
        1: 0,
        0: 1
    }
    # IN_TYPES & OUT_TYPES are used for static type checking so that
    # warnings can be raised when mismatched layers are connected.
    #TODO - Static type checking? Standard type names?
    IN_TYPES = set()
    OUT_TYPE = None

    # Does this layer have multiple children to choose from, or just one?
    # Override this when subclassing
    SINGLE_CHILD = True

    def __init__(self):
        if self.SINGLE_CHILD:
            self.child = None
        else:
            self.children = {}

    def register_child(self, child, key=None):
        if self.SINGLE_CHILD:
            self.child = child
        else:
            self.children[key] = child
        child.parent = self
        return child

    def resolve_child(self, src, header):
        # Each packet can only resolve to *ONE* child
        if self.SINGLE_CHILD:
            return self.child
        else:
            for key, child in self.children.items():
                if self.match_child(src, header, key):
                    return child

    def match_child(self, src, header, key):
        # Override me 
        raise NotImplementedError

    @gen.coroutine
    def on_read(self, src, header, payload):
        # Override me 
        yield self.bubble(src, header, payload)

    @gen.coroutine
    def on_close(self, src, header):
        # Override me  -- if additional things need to be called on close
        # Called when a "connection" or "session" is terminated
        yield self.close_bubble(src, header)

    @gen.coroutine
    def write(self, dst, header, payload):
        # Override me  -- if `on_read` pulled any data out of `payload` into `header`.
        # How does this layer handle messages?
        yield self.write_back(dst, header, payload)

    @gen.coroutine
    def close_bubble(self, src, header):
        child = self.resolve_child(src, header)
        if child is not None:
            yield child.on_close(src, header)

    @gen.coroutine
    def bubble(self, src, header, payload):
        # Bubble tries to pass on a message in the following way:
        # 1. If the next layer exists, pass the message to the next layer
        # 2. Otherwise, use self.write(...), (which probably just writes back to previous layer)
        child = self.resolve_child(src, header)
        if child is not None:
            yield child.on_read(src, header, payload)
        else:
            yield self.write(self.route(src, header), header, payload)

    @gen.coroutine
    def write_back(self, dst, header, payload):
        if self.parent is None:
            raise Exception("Unable to write_back, no parent on %s" % self)
        yield self.parent.write(dst, header, payload)

    @gen.coroutine
    def passthru(self, src, header, payload):
        # Stop trying to parse this message, just write back what's been parsed so far
        # Ignore this layer & all children 
        yield self.write_back(self.route(src, header), header, payload)

    def route(self, src, header):
        # Given a message from port `src`, determine which port to send it to
        return self.routing[src]

    def unroute(self, dst, header):
        # Given a message to port `dst`, determine which port it should have come from
        return self.routing[dst]

class LineBufferLayer(NetLayer):
    # Buffers incoming data line-by-line
    SINGLE_CHILD = True

    def __init__(self, *args, **kwargs):
        super(LineBufferLayer, self).__init__(*args, **kwargs)
        self.buff = ""
        
    @gen.coroutine
    def on_read(self, src, header, data):
        if data is None:
            buff = self.buff
            self.buff = ""
            yield self.bubble(src, header, buff)
        else:
            self.buff += data
            if '\n' in self.buff:
                lines = self.buff.split('\n')
                self.buff = lines[-1]
                for line in lines[:-1]:
                    yield self.bubble(src, header, line + "\n")
            else:
                pass

    @gen.coroutine
    def on_close(self, src, header):
        if self.buff:
            yield self.bubble(src, header, self.buff)
        yield self.close_bubble(src, header)

class CloudToButtLayer(NetLayer):
    SINGLE_CHILD = True
    @gen.coroutine
    def write(self, dst, header, payload):
        butt_data = payload.replace("cloud", "my butt")
        yield self.write_back(dst, header, butt_data)

#TODO
def connect(prev, layer_list, check_types=False, **global_kwargs):
    layers = []
    for (const, args, kwargs) in layer_list:
        kwargs.update(global_kwargs)
        new = const(*args, parent=prev, **kwargs)
        layers.append(new)
        if prev.OUT_TYPE not in new.IN_TYPES and check_types:
            print "Warning: connecting incompatible {} -> {}".format(repr(prev), repr(new))
        prev.next_layer = new
        prev = new
    return layers

# Simple syntatic sugar
def l(constructor, *args, **kwargs):
    return (constructor, args, kwargs)

class MultiOrderedDict(list):
    def __init__(self, from_list=None):
        self.d = {}
        if from_list is not None:
            for (k, v) in from_list:
                self.push(k, v)

    def first(self, key, default=None):
        key = key.lower()
        if key in self.d:
            return self.d[key][0]
        return default

    def last(self, key, default=None):
        key = key.lower()
        if key in self.d:
            return self.d[key][-1]
        return default

    def push(self, key, value):
        self.append((key, value))
        key = key.lower()
        if key in self.d:
            self.d[key].append(value)
        else:
            self.d[key] = [value]

    def last_value_append(self, new_part):
        # This is very specific to HTTP header parsing
        # Append a string to the last updated value
        old_key, old_value = self[-1][0]
        new_value = old_value + new_part

        self[-1] = (old_key, new_value)
        self.d[old_key.lower()][-1] = new_value

        return key, new_value

    def __contains__(self, key):
        return key.lower() in self.d

    def set(self, key, new_value, index=0):
        j = 0
        key = key.lower()
        for i, (k, v) in enumerate(self):
            if k.lower() == key:
                if j == index:
                    self[i] = (k, new_value)
                    break
                j += 1
        else:
            self.push(key, new_value)
        try:
            self.d[key][index] = new_value
        except IndexError:
            self.d[key][-1] = new_value

class PipeLayer(NetLayer):
    SINGLE_CHILD = True
    COMMAND = ["cat", "-"]
    CONN_ID_KEY = "tcp_conn"
    
    def __init__(self):
        super(PipeLayer, self).__init__()
        self.sps = {}

    @gen.coroutine
    def write(self, dst, header, payload):
        conn_id = header[self.CONN_ID_KEY]
        if conn_id not in self.sps:
            self.sps[conn_id] = subprocess.Popen(self.COMMAND, stdin=subprocess.PIPE, stdout=subprocess.PIPE)

        self.sps[conn_id].stdin.write(payload)

    @gen.coroutine
    def on_close(self, src, header):
        conn_id = header[self.CONN_ID_KEY]
        if conn_id not in self.sps:
            return

        self.sps[conn_id].stdin.close()
        output = self.sps[conn_id].communicate()
        self.sps[conn_id].kill()
        del self.sps[conn_id]

        yield self.passthru(src, header, output)

        
