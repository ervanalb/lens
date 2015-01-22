# This serves as an interface to the Tap board.
# See the __main__ section for an example.

import usb.core
import struct
import time
import math

VENDOR_ID=0xFFFF
PRODUCT_ID=0xFFFC

VENDOR_READ = 0xC0
VENDOR_WRITE = 0x40

ACCEL_ADDR = 0x1D

CTRL_READ_REG_8 = 0x20
CTRL_WRITE_REG_8 = 0x21
CTRL_READ_REG_16 = 0x22
CTRL_SET_LED = 0x23
CTRL_SET_RELAYS = 0x24

class Tap:
    def __init__(self):
        self.dev=usb.core.find(idVendor=VENDOR_ID, idProduct=PRODUCT_ID)
        if self.dev is None:
            raise ValueError('Device not found')

    def read_reg_8(self,reg,addr=ACCEL_ADDR):
        return self.dev.ctrl_transfer(VENDOR_READ,CTRL_READ_REG_8,reg,addr,1)[0]

    def write_reg_8(self,reg,val,addr=ACCEL_ADDR):
        assert self.dev.ctrl_transfer(VENDOR_WRITE,CTRL_WRITE_REG_8,reg,addr,struct.pack('B',val))==1

    def set_bits_register(self,reg,bits,mask=0,addr=ACCEL_ADDR):
        value=self.read_reg_8(reg,addr)
        self.write_reg_8(reg,(value & ~mask) | bits,addr)

    def read_reg_16(self,reg,fmt='>h',addr=ACCEL_ADDR):
        a=self.dev.ctrl_transfer(VENDOR_READ,CTRL_READ_REG_16,reg,addr,2)
        return struct.unpack(fmt,a)[0]

    def set_led(self,led):
        assert self.dev.ctrl_transfer(VENDOR_WRITE,CTRL_SET_LED,led,0)==0

    def set_relays(self,relays):
        assert self.dev.ctrl_transfer(VENDOR_WRITE,CTRL_SET_RELAYS,relays,0)==0

    def passthru(self):
        self.set_relays(0x5555)
        self.set_led(False)

    def mitm(self):
        self.set_relays(0xAAAA)
        self.set_led(True)

if __name__=='__main__':
    d=Tap()

    while True:
        d.passthru()
        time.sleep(0.5)
        d.mitm()
        time.sleep(0.5)
