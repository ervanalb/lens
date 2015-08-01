import tornado.gen as gen
from tornado.ioloop import IOLoop
import subprocess

class LayerMeta(type):
    layer_classes = {}
    instance_callback = None

    def __init__(cls, name, bases, dct):
        if "NAME" in dct:
            LayerMeta.layer_classes[dct["NAME"]] = cls
        super(LayerMeta, cls).__init__(name, bases, dct)

    def __call__(cls, *args, **kwargs):
        instance = super(LayerMeta, cls).__call__(*args, **kwargs)
        if LayerMeta.instance_callback is not None:
            LayerMeta.instance_callback(instance)
        return instance

class NetLayer(object):
    __metaclass__ = LayerMeta

    routing = {
        1: 0,
        0: 1
    }

    def __init__(self, debug=False):
        self.children = []
        self.debug = debug
        self.loggers = []

    def register_child(self, child):
        self.children.append(child)
        child.parent = self

    def unregister_child(self, child):
        self.children.remove(child)

    def resolve_child(self, src, header):
        for child in self.children:
            if child.match(src, header):
                return child

    def match(self, src, header):
        # Override me 
        return True # match everything

    # coroutine
    def on_read(self, src, header, payload):
        # Override me 
        return self.bubble(src, header, payload)

    # coroutine
    def on_close(self, src, header):
        # Override me  -- if additional things need to be called on close
        # Called when a "connection" or "session" is terminated
        return self.close_bubble(src, header)

    # coroutine
    def write(self, dst, header, payload):
        # Override me  -- if `on_read` pulled any data out of `payload` into `header`.
        # How does this layer handle messages?
        return self.write_back(dst, header, payload)

    @gen.coroutine
    def close_bubble(self, src, header):
        child = self.resolve_child(src, header)
        if child is not None:
            child.on_close(src, header)

    # coroutine
    def bubble(self, src, header, payload):
        # Bubble tries to pass on a message in the following way:
        # 1. If the next layer exists, pass the message to the next layer
        # 2. Otherwise, use self.write(...), (which probably just writes back to previous layer)
        child = self.resolve_child(src, header)
        if child is not None:
            #print self.NAME,"->",child.NAME
            return child.on_read(src, header, payload)
        else:
            #print self.NAME, "loop"
            return self.write(self.route(src, header), header, payload)

    @gen.coroutine
    def write_back(self, dst, header, payload):
        if self.parent is None:
            raise Exception("Unable to write_back, no parent on %s" % self)
        yield self.parent.write(dst, header, payload)

    # coroutine
    def passthru(self, src, header, payload):
        # Stop trying to parse this message, just write back what's been parsed so far
        # Ignore this layer & all children 
        return self.write_back(self.route(src, header), header, payload)

    def route(self, src, header):
        # Given a message from port `src`, determine which port to send it to
        return self.routing[src]

    def unroute(self, dst, header):
        # Given a message to port `dst`, determine which port it should have come from
        return self.routing[dst]

    def log(self, msg, *args, **kwargs):
        # Log a message to the screen or to a file
        # Mediated by `self.debug` and the layer's `debug` command

        log_message = msg.format(*args, **kwargs)

        for debug_only, log_handler in self.loggers:
            if self.debug or not debug_only:
                log_handler(log_message)

    def add_logger(self, handler, debug_only=False):
        # Add a function to be called on `log` events
        # `debug_only` - if True, then only called when the layer's `debug`
        # property is set.
        self.loggers.append((debug_only, handler))

    def make_toggle(self, name, default=False):
        # Generates property & shell command to toggle the property
        # Usage: (in __init__)
        # self.make_toggle("prop")
        def _do_toggle(*args):
            v = not getattr(self, name)
            setattr(self, name, v)
            return "{} {}: {}".format(self.__class__.__name__, name, "on" if v else "off")

        setattr(self, "do_" + name, _do_toggle)
        setattr(self, name, default)
        return default

    def do_debug(self, *args):
        """Toggle debugging on this layer."""
        # Shell command handler for 'debug' to toggle self.debug
        self.debug = not self.debug
        return "Debug: {}".format("on" if self.debug else "off")

    def add_future(self, future):
        if future is not None:
            def result(f):
                if f.exception():
                    exc_type, exc_value, exc_traceback = f.exc_info()
                    traceback.print_exception(exc_type, exc_value, exc_traceback)
            IOLoop.instance().add_future(future, result)

class LineBufferLayer(NetLayer):
    # Buffers incoming data line-by-line
    NAME = "linebuffer"
    CONN_ID_KEY = "tcp_conn"

    def __init__(self, *args, **kwargs):
        super(LineBufferLayer, self).__init__(*args, **kwargs)
        self.buffers = {}
        self.enabled = {}
        self.closed = {}
        
    @gen.coroutine
    def on_read(self, src, header, data):
        conn_id = header[self.CONN_ID_KEY]
        if conn_id not in self.buffers:
            self.buffers[conn_id] = {0: "", 1: ""}
            self.enabled[conn_id] = {0: True, 1: True}
            self.closed[conn_id] = {0: False, 1: False}

        def lbl_enable(s):
            self.enabled[conn_id][s] = True
        def lbl_disable(s):
            self.enabled[conn_id][s] = False

        header["lbl_enable"] = lbl_enable
        header["lbl_disable"] = lbl_disable

        if data is None:
            buff = self.buffers[conn_id][src]
            self.buffers[conn_id][src] = ""
            yield self.bubble(src, header, buff)
        else:
            #print "> recvd data from ", src, len(data), len(self.buffers[conn_id][src])
            self.buffers[conn_id][src] += data
            if self.enabled[conn_id][src]:
                while '\n' in self.buffers[conn_id][src]:
                    line, _newline, self.buffers[conn_id][src] = self.buffers[conn_id][src].partition('\n')
                    #print ">>>", line1460
                    yield self.bubble(src, header, line + "\n")

            if not self.enabled[conn_id][src]:
                buff = self.buffers[conn_id][src]
                self.buffers[conn_id][src] = ""
                yield self.bubble(src, header, buff)

    @gen.coroutine
    def on_close(self, src, header):
        conn_id = header[self.CONN_ID_KEY]
        if conn_id in self.buffers:
            buff = self.buffers[conn_id][src]
            self.buffers[conn_id][src] = ""
            yield self.bubble(src, header, buff)

            self.closed[conn_id][src] = True
            if all(self.closed[conn_id]): 
                del self.closed[conn_id]
                del self.enabled[conn_id]
                del self.buffers[conn_id]
        yield self.close_bubble(src, header)

class MultiOrderedDict(list):
    def __init__(self, from_list=None):
        self.d = {}
        if from_list is not None:
            for (k, v) in from_list:
                self.push(k, v)

    def remove(self, key):
        key = key.lower()
        if key in self.d:
            print "Removing", key, ":", self.d[key]
            del self.d[key]
            for (i, (k, v)) in enumerate(self):
                if k.lower() == key:
                    self.pop(i)

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

class PrintLayer(NetLayer):
    NAME = "print"

    # coroutine
    def write(self, dst, header, payload):
        print ">", payload
        return self.write_back(dst, header, payload)

    # coroutine
    def on_read(self, src, header, payload):
        print "<", payload
        return self.bubble(src, header, payload)    

class RecorderLayer(NetLayer):
    NAME = "recorder"

    def __init__(self):
        super(RecorderLayer, self).__init__()
        self.f = None

    def do_start(self, filename):
        self.f = open(filename, "w")
        self.byte_counter = 0
        self.packet_counter = 0

    def do_stop(self):
        if not self.f:
            raise Exception("Not recording!")
        self.f.close()
        self.f = None
        print "Recorded {0} packets ({1} bytes)".format(self.packet_counter, self.byte_counter)

    # corountine
    def on_read(self, src, header, payload):
        if self.f:
            self.f.write(payload)
            self.byte_counter += len(payload)
            self.packet_counter += 1
        return self.bubble(src, header, payload)

class PipeLayer(NetLayer):
    NAME = "pipe"
    COMMAND = ["cat", "-"]
    CONN_ID_KEY = "tcp_conn"
    
    def __init__(self):
        super(PipeLayer, self).__init__()
        self.sps = {}
        self.debug = False

    @gen.coroutine
    def write(self, dst, header, payload):
        if self.debug:
            print "PIPE>", len(payload)
        conn_id = header[self.CONN_ID_KEY]
        if conn_id not in self.sps:
            self.sps[conn_id] = subprocess.Popen(self.COMMAND, stdin=subprocess.PIPE, stdout=subprocess.PIPE)

        #self.sps[conn_id].stdin.write(payload)
        output, _stderr = self.sps[conn_id].communicate(input=payload)
        if self.debug:
            print "Pipe stderr: ", _stderr
            print "PIPE<", len(output)
        del self.sps[conn_id]
        return self.write_back(dst, header, output)

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

