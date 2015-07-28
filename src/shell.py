class CommandShell(object):
    prompt = "> "

    def __init__(self):
        self.input_file = open("/dev/stdin")
        self.output_file = open("/dev/stdout", "w")
        self.layers = {}
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
            result = "Registered layers:", self.layers.keys().join(", ")
        elif layer in self.layers:
            sh_obj = self.layers[layer].Shell
            if command is None:
                cmds = [x[3:] for x in dir(sh_obj) if x.startswith("on_")]
                result = "Layer '%s' commands:" % layer, cmds.join(", ")
            else:
                fn = getattr(sh_obj.Shell, "on_%s" % command, None)
                if fn is not None:
                    try:
                        result = fn(lobj, arguments)
                    except Exception as e:
                        result = "Layer Error: %s" % e
                else:
                    result = "Invalid layer command '%s %s'" % (layer, command)
        else:
            result = "Invalid layer '%s'" % layer

        self.output_file.write(result + "\n")
        self.write_prompt()

    def ioloop_attach(self, ioloop):
        self.ioloop = ioloop
        ioloop.add_handler(self.input_file.fileno(), self.handle_input, ioloop.READ)
        self.write_prompt()

    def register_layer(self, layer, name):
        name = name.lower()
        if name in self.layers:
            print "Warning: replacing layer '%s' in shell" % name
        self.layers[name] = layer


