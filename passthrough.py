import ethernet 
import driver

def passthrough(sent_data, write_back, write_fwd):
    print("recvd data", len(sent_data))
    write_fwd(sent_data)

if __name__ == "__main__":
    tap = driver.Tap()
    tap.mitm()

    eth = ethernet.Ethernet(passthrough, passthrough, debug=False)
    eth.run()
