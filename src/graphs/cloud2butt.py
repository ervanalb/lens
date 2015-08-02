#!/usr/bin/python2

import base
import ethernet 
import http
import ip
import rtp
import tcp
import udp
import util
import video

eth_layer = ethernet.EthernetLayer()
root.register_child(eth_layer)

ipv4_layer = ip.IPv4Layer()
eth_layer.register_child(ipv4_layer)

#ipv4_filter_layer = ip.IPv4FilterLayer(ips=addr)
#ipv4_layer.register_child(ipv4_filter_layer)
ipv4_filter_layer = ipv4_layer

tcp_layer = tcp.TCPLayer()
ipv4_filter_layer.register_child(tcp_layer)

http_filter_layer = tcp.TCPFilterLayer(80, 8000, 8080)
http_filter_layer.name = "http_port_filter"
tcp_layer.register_child(http_filter_layer)

http_lbf_layer = util.LineBufferLayer()
http_filter_layer.register_child(http_lbf_layer)

http_layer = http.HTTPLayer()
http_lbf_layer.register_child(http_layer)

c2b_layer = http.CloudToButtLayer()
http_layer.register_child(c2b_layer)
