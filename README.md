# lens
lens stands for "live editing of network streams"

Tap live cabling for inspection and injection.



Software Model
==============

Network Layers
--------------

The software is divided into *layers*, each of which manages its own state and provides an abstraction for the layers above it. These layers follow from the standard "OSI Model" network layers, *ethernet*, *IPv4*, *TCP*, *HTTP*, etc.

### State & Connections

Some layers are inherently stateful with respect to the data that is passed through them (e.g. TCP), whereas others do not require any state to handle their data (e.g. IPv4). However, these layers may find it useful to maintain state in order to later forge packets.

Layers are represented as subclasses of ``NetLayer``. Layers are chained together to form a doubly-linked DAG, where each layer knows its *parent* (``prev_layer``) and its *child* (``next_layer``) or *children* (currently ``#TODO``) that come "above" it in the stack. For example, in the stateless case, an instance of ``IPv4Layer`` may have an ``EthernetLayer`` instance as it's parent/``prev_layer``, with that instance's ``next_layer`` pointing back to the ``IPv4Layer`` instance.

For the purposes of this document, this will be described as ``EthernetLayer --> IPv4Layer``, even though the connection is in fact double-ended, and the layers are instances.

If a layer is stateful, it will create a new instance of its child layer for each "session." This way, each layer instance represents a session in the previous layer. For example, in ``TCPLayer --> HTTPLayer``, each HTTPLayer is given an abstraction that is similar to opening a TCP socket.

### Methods

Each layer (subclassing ``NetLayer``) should implement the following methods as tornado coroutines:

- ``Layer.on_read(self, src, data, header)``

This coroutine is called whenever there is new data (``data``) available for the layer to process. ``header`` is a ``dict`` which holds all of the information extracted from all of the previous layers. With ``data`` and ``header``, it should be possible to completely reconstruct the original packet. ``src`` represents where the data came from -- currently this only takes one of two values: ``0`` representing the *Alice* NIC, or ``1`` representing the *Bob* NIC.

- ``Layer.write(self, dst, data, header)``

This coroutine is called to write out ``data``. In normal flow, the parameters that were extracted into ``header`` during ``on_read`` are then re-serialized and combined with ``data`` to form the appropriate payload, followed by a call to ``prev_layer.write(dst, payload, header)``.

- ``Layer.on_close(self, src, header)``

This coroutine is called when the previous layer terminates a connection, i.e. when a TCP connection is closed. ``header`` may contain additional information about the circumstances of the termination (e.g. in TCP, RST vs. FIN)

#### Routing

Currently, ``src`` and ``dst`` parameters represent which NIC the message came from or is intended to go to. ``NetLayer`` implements two functions, ``route(src)`` and ``unroute(dst)``, which are intended to resolve the intended recipient of a packet. This mechanism might need to be re-worked for systems with 3+ NICs. Currently, the two NICs are represented by ``0`` and ``1``, so both functions are functionally equivalent.

#### Convenience Methods

Although each ``NetLayer`` should implement the methods above, there are some additional helper methods/coroutines that are useful:

- ``Layer.bubble(self, src, data, header)``

This coroutine will call ``self.next_layer.on_read(...)`` if ``next_layer`` is set. Otherwise, it calls ``self.write(dst, ...)``, resolving ``dst`` from ``src``. Usually this method is used to pass data on to higher layers as it has the correct behavior when no higher layer is connected. 

- ``Layer.passthru(self, src, data, header)``

This coroutine will call ``self.prev_layer.write(dst, ...)`` if ``prev_layer`` is set. It also resolves ``dst`` from ``src``.


