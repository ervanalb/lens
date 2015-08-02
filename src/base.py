import tornado.gen as gen
from tornado.ioloop import IOLoop

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
        self.name = self.NAME

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
