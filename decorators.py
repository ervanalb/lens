import scapy.all as sc

def tcp_ignore_port(port):
    # Let traffic on a specific TCP port pass through cleanly
    # Useful to not interfere with SSH sesions while debugging
    def _filter_fn(fn):
        def _fn(sent_data, write_back, write_fwd):
            e = sc.Ether(sent_data)
            if "TCP" in e:
                l = e["TCP"]
                if l.sport == port or l.dport == port:
                    # Match: pass through
                    return write_fwd(sent_data)
            # No match
            return fn(sent_data, write_back, write_fwd)
        return _fn
    return _filter_fn

def ipv4_prudish_mode(addr, drop=True):
    # Opposite of promisc. mode
    # Filter out IP packets not routed to a particular IP
    def _filter_fn(fn):
        def _fn(sent_data, write_back, write_fwd):
            e = sc.Ether(sent_data)
            if "IP" not in e:
                return write_fwd(sent_data)

            l = e["IP"]

            if l.src == addr or l.dst == addr:
                # Match: pass it on
                return fn(sent_data, write_back, write_fwd)
            elif not drop:
                return write_fwd(sent_data)
            # Drop the packet
        return _fn
    return _filter_fn

def tcp(fn):
    def _fn(sent_data, write_back, write_fwd):
        e = sc.Ether(sent_data)
        if "TCP" not in e:
            return write_fwd(sent_data)

        l = e["TCP"]

        if not l.payload:
            return write_fwd(sent_data)

        def _back(data):
            l.payload = data
            if "IP" in e:
                del(e["IP"].chksum)
            del(e["TCP"].chksum)
            return write_back(str(e))

        def _fwd(data):
            if "butt" in data:
                print str(e)
            l.payload = data
            if "IP" in e:
                del(e["IP"].len)
                del(e["IP"].chksum)
            del(e["TCP"].chksum)
            #e.show()
            if "butt" in data:
                print str(e)
            return write_fwd(str(e))

        fn(l.payload.load, _back, _fwd)
    return _fn
