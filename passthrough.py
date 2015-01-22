import ethernet 
import driver
from scapy.packet import Packet
import scapy.all as sc

def passthrough(sent_data, write_back, write_fwd):
    print("recvd data", len(sent_data))
    #p = Packet(sent_data)
    p = sc.Ether(sent_data)
    print repr(p)
    write_fwd(sent_data)

if __name__ == "__main__":
    tap = driver.Tap()
    tap.mitm()

    eth = ethernet.Ethernet(passthrough, passthrough, debug=False)
    eth.run()
