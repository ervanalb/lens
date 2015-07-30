class ShellQuit(Exception):
    pass

class CommandShell(object):
    CMD_PREFIX = "do_"
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
            result = "Registered layers: {}".format(", ".join(self.layers.keys()))
        elif layer == "quit":
            raise ShellQuit
        elif layer in self.layers:
            layer_obj = self.layers[layer]
            if command is None:
                cmds = [x[3:] for x in dir(layer_obj) if x.startswith(self.CMD_PREFIX)]
                result = "Layer '{}' commands: {}".format(layer, ", ".join(cmds))
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

    def register_layer(self, layer, name):
        name = name.lower()
        if name in self.layers:
            print "Warning: replacing layer '%s' in shell" % name
        self.layers[name] = layer


