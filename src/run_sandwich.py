#!/usr/bin/python2

import sys
import driver
import shell
import link
from tornado.ioloop import IOLoop

import base
import ethernet 
import http
import ip
import rtp
import tcp
import udp
import util
import video

if __name__ == "__main__":

    root = link.LinkLayer()

    if len(sys.argv) == 2:
        graph = sys.argv[1]
        v = {"root":root}
        execfile(graph, v)
    elif len(sys.argv) > 2:
        print "Only one argument allowed (graph file to load)"
        sys.exit(1)

    #tap = driver.FakeTap()
    tap = driver.Tap()
    tap.mitm()
    
    sh = shell.CommandShell(root)
    try:
        IOLoop.instance().start()
    finally:
        tap.passthru()
