import base

import fcntl
import os
from tornado.ioloop import IOLoop
import traceback
import sys
import signal

class ShellQuit(Exception):
    pass

class CommandShell(object):
    CMD_PREFIX = "do_"
    prompt = "> "

    def __init__(self, root):
        self.input = sys.stdin
        self.output = sys.stdout

        fcntl.fcntl(self.output.fileno(), fcntl.F_SETFL, os.O_NONBLOCK)

        self.root = root
        self.layer_classes = base.LayerMeta.layer_classes
        self.input_buffer = ""

        self.ioloop = IOLoop.current()
        self.ioloop.add_handler(self.input.fileno(), self.handle_input, IOLoop.READ)


        def enable_sig_handler():
            def _sig_handler(signum, frame):
                self.ioloop.current().add_callback(self.sig_handler, signum, frame)
            signal.signal(signal.SIGTERM, _sig_handler)
            signal.signal(signal.SIGINT, _sig_handler)
        self.ioloop.add_callback(enable_sig_handler)

        self.write_prompt()
        base.LayerMeta.instance_callback = self.instance_callback

    @property
    def layers(self):
        found = []
        def find_layers(node):
            found.append(node)
            for n in node.children:
                find_layers(n)

        def get_unique_name(layers, layer):
            if layer.name in layers:
                i=2
                while True:
                    name = "{0}_{1}".format(layer.name, i)
                    if name not in layers:
                        break
                return name
            else:
                return layer.name

        find_layers(self.root)
        layers_dict = {}
        for layer in found:
            name = get_unique_name(layers_dict, layer)
            layers_dict[name] = layer
        return layers_dict

    def instance_callback(self, layer_instance):
        #print "register layer", layer_instance
        #self.register_layer_instance(layer_instance)

        def _log_handler(message):
            self.output.write("\r[{0:s}] {1}\n".format(layer_instance.NAME, message))
            self.write_prompt()

        layer_instance.add_logger(_log_handler, debug_only=True)

    def sig_handler(self, signum, frame):
        self.input_buffer = ""
        self.output.write("\n")
        self.write_prompt()

    def write_prompt(self):
        self.output.write(self.prompt)
        self.output.write(self.input_buffer)
        self.output.flush()

    def handle_input(self, fd, events):
        new_data = self.input.read()

        if new_data == "": # Ctrl-D
            self.output.write("\n")
            self.ioloop.stop()
            return

        self.input_buffer += new_data

        while "\n" in self.input_buffer:
            i = self.input_buffer.index("\n") + 1
            line, self.input_buffer = self.input_buffer[:i], self.input_buffer[i:]
            self.handle_command(line)

    def handle_command(self, input_line):
        arguments = input_line.split()

        if len(arguments) == 0:
            if "\n" not in input_line:
                self.output.write("\n")
            self.write_prompt()
            return

        layer, command = None, None
        command = arguments.pop(0).lower()

        get_cmd_fn = lambda obj, name: getattr(obj, self.CMD_PREFIX + name, None)

        shell_fn = get_cmd_fn(self, command)
        if shell_fn is not None:
            # Then this is actually a shell command
            try:
                result = shell_fn(*arguments)
            except ShellQuit:
                self.ioloop.stop()
                return
            except Exception as e:
                result = traceback.format_exc()
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
            self.output.write(str(result) + "\n")
        self.write_prompt()

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
        """add <layer> <new_layer_name> (<args>...)- Create <new_layer_name> as a child of <layer>."""
        l = self.layer_classes[layername](*args)
        parent = self.layers[parentname]
        parent.register_child(l)
        print "Added '{0}'".format(self.layer_name(l))

    def do_del(self, layername):
        """del <layer> - Delete a layer."""
        l = self.layers[layername]
        if not hasattr(l, "parent"):
            return "'{0}' has no parent and therefore can't be deleted".format(layername)
        l.parent.unregister_child(l)
        return "Deleted '{0}'".format(layername)

    def do_del(self, layername):
        """del <layer> - Delete <layer> and all its descendants."""
        l = self.layers[layername]
        if not hasattr(l, "parent"):
            return "'{0}' has no parent and therefore can't be deleted".format(layername)
        l.parent.unregister_child(l)
        return "Deleted '{0}'".format(layername)

    def do_del_rejoin(self, layername):
        """del_rejoin <layer> - Delete <layer>, and have its parent inherit its children."""
        l = self.layers[layername]
        if not hasattr(l, "parent"):
            return "'{0}' has no parent and therefore can't be deleted".format(layername)
        p = l.parent
        for c in l.children:
            l.unregister_child(c)
            p.register_child(c)
        l.parent.unregister_child(l)
        return "Deleted '{0}'".format(layername)

    def do_add_before(self, layer, layername, *args):
        """add_before <layer> <new_layer_name> (<args>...)- Insert <new_layer_name> immediately before <layer>."""
        youngest = self.layers[layer]
        middle = self.layer_classes[layername](*args)
        oldest = youngest.parent
        oldest.unregister_child(youngest)
        oldest.register_child(middle)
        middle.register_child(youngest)
        print "Added '{0}' before '{1}'".format(self.layer_name(middle), layer)

    def do_add_after(self, layer, layername, *args):
        """add_after <layer> <new_layer_name> (<args>...)- Insert <new_layer_name> immediately after <layer>."""
        oldest = self.layers[layer]
        middle = self.layer_classes[layername](*args)
        for youngest in oldest.children:
            oldest.unregister_child(youngest)
            middle.register_child(youngest)
        oldest.register_child(middle)

        print "Added '{0}' after '{1}'".format(self.layer_name(middle), layer)

    def do_show(self, layername = None):
        """show [layername] - Show tree of connected layers."""
        def printer(l, last = [True]):
            l_n = self.layer_name(l)
            prefix = "".join(["   " if last_layer else "|  " for last_layer in last[:-1]])
            print prefix + "|- " + l_n
            if len(l.children):
                for child in l.children[:-1]:
                    printer(child, last + [False])
                printer(l.children[-1], last + [True])

        if layername is None:
            l = self.root
        else:
            try:
                l = self.layers[layername]
            except KeyError:
                return "No such layer '{}'".format(layername)
        printer(l)

    def do_load(self, graph_file):
        """load <graph_file> - Rebuild the tree according to <graph_file>"""
        for child in self.root.children:
            self.root.unregister_child(child)

        v = {"root": self.root}
        execfile(graph_file, v)
        print "Loaded '{0}'".format(graph_file)
