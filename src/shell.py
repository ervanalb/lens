class ShellQuit(Exception):
    pass

class CommandShell(object):
    CMD_PREFIX = "do_"
    prompt = "> "

    def __init__(self):
        self.input_file = open("/dev/stdin", "r")
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

        if len(arguments) == 0:
            self.write_prompt()
            return

        command = arguments.pop(0).lower()

        get_cmd_fn = lambda obj, name: getattr(obj, self.CMD_PREFIX + name, None)

        shell_fn = get_cmd_fn(self, command)
        if shell_fn is not None:
            # Then this is actually a shell command
            try:
                result = shell_fn(*arguments)
            except ShellQuit:
                raise
            except Exception as e:
                result = "Shell Error: {}".format(e)
        else:
            layer, command = command, None
            if len(arguments) > 0:
                command = arguments.pop(0).lower()

            if layer in self.layers:
                if command is None or command == "help":
                    # Get help for `layer` if no command was specified
                    result = self.do_help(layer)
                else:
                    layer_obj = self.layers[layer]
                    fn = get_cmd_fn(layer_obj, command)
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
        ioloop.add_handler(0, self.handle_input, ioloop.READ)
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
        return {v: k for k, v in self.layers.items()}.get(layer, None)

    def do_help(self, layer=None):
        """help (<layer>) - Display help."""
        def print_help(obj):
            for key in sorted(dir(obj)):
                if key.startswith(self.CMD_PREFIX):
                    cmd_name = key[len(self.CMD_PREFIX):]
                    help_text = getattr(obj, key).__doc__ or "(undocumented)"
                    print "    {:8s} {}".format(cmd_name, help_text)

        if layer is None:
            print "Registered layers:"
            print "    {}".format(" ".join(self.layers.keys()))
            print ""
            print "Shell Commands:"
            print_help(self)

        elif layer in self.layers:
            layer_obj = self.layers[layer]
            print "{} ({}) Commands:".format(layer, layer_obj.__class__.__name__)
            print_help(layer_obj)

        else:
            print "Unknown layer: '{}'".format(layer)

    def do_quit(self, *args):
        """quit - Close lens, switching tap to passthru."""
        raise ShellQuit

    def do_add(self, parentname, layername, *args):
        """add <parent> <layername> (<args>...)- Create a layer."""
        ls = {l.NAME: l for l in self.available_layers}
        l = ls[layername](*args)
        parent = self.layers[parentname]
        parent.register_child(l)
        n = self.register_layer_instance(l)
        print "Registered '{}'".format(n)

    def do_del(self, layername):
        """del <layername> - Delete a layer."""
        l = self.layers[layername]
        self.unregister_layer_instance(l)
        l.parent.unregister_child(l)

    def do_show(self, layername):
        """show <layername> - Show tree of connected layers."""
        def printer(l, last = [True]):
            l_n = self.layer_name(l)
            prefix = "".join(["   " if last_layer else "|  " for last_layer in last[:-1]])
            print prefix + "|- " + l_n
            if len(l.children):
                for child in l.children[:-1]:
                    printer(child, last + [False])
                printer(l.children[-1], last + [True])

        try:
            l = self.layers[layername]
        except KeyError:
            return "No such layer '{}'".format(layername)

        printer(l)
