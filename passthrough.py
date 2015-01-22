import ethernet 

def passthrough(sent_data, write_back, write_fwd):
    print("recvd data", len(sent_data))
    write_fwd(sent_data)

if __name__ == "__main__":
    eth = ethernet.Ethernet(passthrough, passthrough, debug=False)
    eth.run()
