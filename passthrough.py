
def passthrough(sent_data, write_back, write_fwd):
    write_fwd(sent_data)

if __name__ == "__main__":
    eth = ethernet.Ethernet(passthrough, passthrough, debug=True)
    eth.run()
