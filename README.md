# lens
lens stands for "live editing of network streams"

Tap live cabling for inspection and injection.



Software Model
==============

Network Layers
--------------

The software is divided into *layers*, each of which manages its own state and provides an abstraction for the layers above it. These layers follow from the standard "OSI Model" network layers, *Ethernet*, *IPv4*, *TCP*, *HTTP*, etc.

### State & Connections

Some layers are inherently stateful with respect to the data that is passed through them (e.g. TCP), whereas others do not require any state to handle their data (e.g. IPv4). However, these layers may find it useful to maintain state in order to later forge packets.

Layers are represented as subclasses of ``NetLayer``. Layers are chained together to form a doubly-linked DAG, where each layer knows its *parent* (``parent``) and its *child* (``child``) or *children* (``children``) that come "above" it in the stack. For example, an instance of ``IPv4Layer`` may have an ``EthernetLayer`` instance as it's ``parent``, with that instance's ``children`` containing a reference back to the ``IPv4Layer`` instance.

For the purposes of this document, this will be described as ``EthernetLayer --> IPv4Layer``, even though the connection is in fact double-ended, and the layers are instances.

### Methods

Each layer (subclassing ``NetLayer``) should implement the following methods as tornado coroutines:

- ``Layer.on_read(self, src, header, payload)``

This coroutine is called whenever there is new data (``payload``) available for the layer to process. ``header`` is a ``dict`` which holds all of the information extracted from all of the previous layers. With ``payload`` and ``header``, it should be possible to completely reconstruct the original packet. ``src`` represents where the data came from. Usually calls ``Layer.bubble(src, new_header, sub_payload)`` to pass data to children layers.

- ``Layer.write(self, dst, header, payload)``

This coroutine is called to write out ``payload``. In normal flow, the parameters that were extracted into ``header`` during ``on_read`` are then re-serialized and combined with ``payload`` to form the appropriate payload, followed by a call to ``Layer.write_back(dst, header, payload)``.

- ``Layer.on_close(self, src, header)``

This coroutine is called when the previous layer terminates a connection, i.e. when a TCP connection is closed. ``header`` may contain additional information about the circumstances of the termination (e.g. in TCP, RST vs. FIN). Usually finishes with a call to ``Layer.close_bubble(src, header)``.

#### Routing

Currently, ``src`` and ``dst`` parameters represent which NIC the message came from or is intended to go to. ``NetLayer`` implements two functions, ``route(src)`` and ``unroute(dst)``, which are intended to resolve the intended recipient of a packet. This mechanism might need to be re-worked for systems with 3+ NICs. Currently, the two NICs are represented by ``0`` and ``1``, so both functions are functionally equivalent.

#### Convenience Methods

Although each ``NetLayer`` should implement the methods above, there are some additional helper methods/coroutines that are useful:

- ``Layer.bubble(self, src, header, payload)``

This coroutine will determine which child to use based on ``src`` and ``header``, then call ``child.on_read(...)``. If no child exists, it calls ``self.write(dst, ...)``, resolving ``dst`` from ``src``, at which point the program flow "reverses direction". Usually this method is used to pass data on to higher layers as it has the correct behavior when no higher layer is connected. 

- ``Layer.close_bubble(self, src, header)``

(*todo*)

- ``Layer.passthru(self, src, header, payload)``

This coroutine will call ``self.parent.write(dst, ...)`` if ``parent`` is set. It also resolves ``dst`` from ``src``.

- ``Layer.write_back(self, dst, header, payload)`` 

(*todo*)



