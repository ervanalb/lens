class ShellQuit(Exception):
    pass

class CommandShell(object):
    CMD_PREFIX = "do_"
    prompt = "> "

    def __init__(self):
        self.input_file = open("/dev/stdin")
        self.output_file = open("/dev/stdout", "w")
        self.layers = {}
        self.available_layers = []
        self.ioloop = None

    def write_prompt(self):
        self.output_file.write(self.prompt)
        self.output_file.flush()

    def handle_input(self, fd, events):
        input_line = self.input_file.readline()
        arguments = input_line.split()
        layer, command = None, None
        if len(arguments) > 0:
            layer = arguments.pop(0).lower()
        if len(arguments) > 0:
            command = arguments.pop(0).lower()

        if layer == "help" or layer is None:
            result = "Registered layers: {}".format(", ".join(self.layers.keys()))
        elif layer == "quit":
            raise ShellQuit
        elif layer in self.layers:
            layer_obj = self.layers[layer]
            if command is None:
                cmds = [x[3:] for x in dir(layer_obj) if x.startswith(self.CMD_PREFIX)] + self.global_layer_cmds.keys()
                result = "Layer '{}' commands: {}".format(layer, ", ".join(cmds))
            else:
                if command in self.global_layer_cmds:
                    try:
                        result = self.global_layer_cmds[command](self, layer_obj, *arguments)
                    except Exception as e:
                        result = "Error: {}".format(e)
                else:
                    fn = getattr(layer_obj, self.CMD_PREFIX + command, None)
                    if fn is not None:
                        try:
                            result = fn(*arguments)
                        except Exception as e:
                            result = "Layer Error: {}".format(e)
                    else:
                        result = "Invalid layer command '{} {}'".format(layer, command)
        else:
            result = "Invalid layer '{}'".format(layer)

        if result is not None:
            self.output_file.write(str(result) + "\n")
        self.write_prompt()

    def ioloop_attach(self, ioloop):
        self.ioloop = ioloop
        ioloop.add_handler(self.input_file.fileno(), self.handle_input, ioloop.READ)
        self.write_prompt()

    def register_layer_instance(self, layer, basename = None):
        if basename is None:
            basename = layer.NAME
        if basename in self.layers:
            i=2
            while True:
                name = "{0}_{1}".format(basename, i)
                if name not in self.layers:
                    break
        else:
            name = basename
        self.layers[name] = layer
        return name

    def unregister_layer_instance(self, layer):
        l_n = self.layer_name(layer)
        del self.layers[l_n]
        for c in layer.children:
            self.unregister_layer_instance(c)
        print "Deleted '{}'".format(l_n)

    def layer_name(self, layer):
        return {v: k for k, v in self.layers.items()}[layer]

    def add_layer(self, parent, layername, *args):
        ls = {l.NAME: l for l in self.available_layers}
        l = ls[layername](*args)
        parent.register_child(l)
        n = self.register_layer_instance(l)
        print "Registered '{}'".format(n)

    def del_layer(self, parent, layername):
        l = self.layers[layername]
        self.unregister_layer_instance(l)
        parent.unregister_child(l)

    def show_layer(self, layername):
        def printer(l, level = 0):
            l_n = self.layer_name(l)
            print "|  " * level + "|- " + l_n
            for child in l.children:
                printer(child, level + 1)

        printer(layername)

    global_layer_cmds = {"add": add_layer, "del": del_layer, "show": show_layer}

