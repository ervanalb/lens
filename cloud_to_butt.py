import ethernet 
import driver
from decorators import tcp

@tcp
def alice(sent_data, write_back, write_fwd):
    if "cloud" in sent_data:
        print sent_data
    write_fwd(sent_data.replace("cloud", "butts"))

@tcp
def bob(sent_data, write_back, write_fwd):
    if "butt " in sent_data:
        print sent_data
    write_fwd(sent_data.replace("butts", "cloud"))

if __name__ == "__main__":
    eth = ethernet.Ethernet(alice, bob)
    eth.run()
