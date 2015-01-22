import ethernet 
import driver
#import scapy.all as sc

def passthrough(sent_data, write_back, write_fwd):
    print("recvd data", len(sent_data))
    #p = Packet(sent_data)
    #p = sc.Ether(sent_data)
    #print repr(p)
    write_fwd(sent_data)

if __name__ == "__main__":
    eth = ethernet.Ethernet(passthrough, passthrough)
    eth.run()
