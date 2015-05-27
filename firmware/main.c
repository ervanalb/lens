
// Config words
#pragma config FOSC = INTOSC //Intrenal RC oscillator Enabled
#pragma config WDTE = ON    //Watch Dog Timer Disabled.
#pragma config PWRTE= ON     //Power Up Timer Enabled
#pragma config MCLRE = ON    //MCLR pin function Enabled
#pragma config CP = OFF      //Flash Program Memory Code Protection Disabled
#pragma config BOREN = ON    //Brown-out Reset enabled
#pragma config CLKOUTEN = OFF//CLKOUT function is disabled.
#pragma config IESO = OFF    //Internal/External Switchover Mode is disabled
#pragma config FCMEN = OFF   //Fail-Safe Clock Monitor is disabled
#pragma config WRT = OFF     //Flash Memory Self-Write Protection Off
#pragma config CPUDIV = CLKDIV3//CPU system clock divided by 3
#pragma config USBLSCLK = 48MHz //System clock expects 48 MHz, FS/LS USB CLKENs divide-by is set to 8
#pragma config PLLMULT = 3x //3x Output Frequency Selected
#pragma config PLLEN = ENABLED //3x or 4x PLL Enabled
#pragma config STVREN = OFF //Stack Overflow or Underflow will not cause a Reset
#pragma config BORV = HI //Brown-out Reset Voltage (Vbor), high trip point selected.
#pragma config LPBOR = OFF //Low-Power BOR is disabled
#pragma config LVP = OFF //High-voltage on MCLR/VPP must be used for programming

#include <stdint.h>
#include "usb.h"
#include "i2c.h"

extern volatile CTRL_TRF_SETUP SetupPkt;
extern volatile BYTE CtrlTrfData[USB_EP0_BUFF_SIZE];

void interrupt ISRCode();
int main();
inline void InitializeSystem();
inline void zero_sr();
inline void WriteRelays(uint16_t bits);
inline void FaultCondition();

unsigned char ctrl_ep_data[CTRL_EP_SIZE];

USB_HANDLE lastINTransmission;

uint16_t fault_bits = 0;
uint16_t heartbeat_counter;

void interrupt ISRCode()
{
    if (USBInterruptFlag)
        USBDeviceTasks();
    if (INTCONbits.TMR0IE && INTCONbits.TMR0IF)
    {
        heartbeat_counter--;
        if(heartbeat_counter == 0)
        {
            FaultCondition();
        }
        INTCONbits.TMR0IF = 0;
    }
}

int main() {
    InitializeSystem();
    #if defined(USB_INTERRUPT)
        USBDeviceAttach();
    #endif
    while(1)
    {
        ClrWdt();
        #if defined(USB_POLLING)
            USBDeviceTasks();
        #endif
        if(PORTCbits.RC2 == 0)
        {
            FaultCondition();
        }
    }
}

#define _XTAL_FREQ 16000000

inline void InitializeSystem()
{
    OSCCON = 0x7C;   // PLL enabled, 3x, 16MHz internal osc, SCS external
    OSCCONbits.SPLLMULT = 1;   // 1=3x, 0=4x
    ACTCON = 0x90;   // Clock recovery on, Clock Recovery enabled; SOF packet

    Init_I2C();

    LATCbits.LATC3 = 0;
    TRISCbits.TRISC3 = 0;

    LATCbits.LATC4 = 0;
    TRISCbits.TRISC4 = 0; // SER

    LATAbits.LATA4 = 0;
    TRISAbits.TRISA4 = 0; // RCK

    LATAbits.LATA5 = 0;
    TRISAbits.TRISA5 = 0; // SCK

    zero_sr();

    LATCbits.LATC5 = 0;
    TRISCbits.TRISC5 = 0; // ~REN

    // Enable TMR0 prescaler
    OPTION_REGbits.TMR0CS = 0;
    OPTION_REGbits.PSA = 0;
    OPTION_REGbits.PS = 4;

    USBDeviceInit();	//usb_device.c.  Initializes USB module SFRs and firmware
}

//inline void SendData(BYTE* data)
//{
//    data[0]=0xCC;
//}

// ******************************************************************************************************
// ************** USB Callback Functions ****************************************************************
// ******************************************************************************************************

void USBCBSuspend(void)
{
}

void USBCBWakeFromSuspend(void)
{
}

void USBCB_SOF_Handler(void)
{
}

void USBCBErrorHandler(void)
{
}

void ReceiveCtrlWriteReg8(void)
{
    Send_I2C_StartBit();                    // send start bit
    Send_I2C_Data((SetupPkt.wIndex << 1) | I2C_WRITE);    // send control byte with R/W bit set low
    Send_I2C_Data(SetupPkt.wValue);         // send word address
    Send_I2C_Data(CtrlTrfData[0]);         // send data
    Send_I2C_StopBit();                    // send stop bit
}

void SetLED(void)
{
    LATCbits.LATC3 = SetupPkt.wValue;
}

inline void short_pause()
{
    uint8_t i;
    for(i=0;i<10;i++);
}

inline void latch_pause()
{
    uint16_t i;
    for(i=0;i<2000;i++);
}

inline void zero_sr()
{
    uint16_t i;
    LATCbits.LATC4 = 0; // SER = 0
    for(i=0;i<16;i++)
    {
        short_pause();
        LATAbits.LATA5 = 1; // SCK high
        short_pause();
        LATAbits.LATA5 = 0; // SCK low
    }
    short_pause();
    LATAbits.LATA4 = 1; // RCK high
    short_pause();
    LATAbits.LATA4 = 0; // RCK low
}

inline void WriteRelays(uint16_t bits)
{
    uint8_t i;
    for(i=0;i<16;i++)
    {
        LATCbits.LATC4 = bits & 1; // SER = LSB
        short_pause();
        LATAbits.LATA5 = 1; // SCK high
        short_pause();
        LATAbits.LATA5 = 0; // SCK low

        bits >>= 1;
    }
    short_pause();
    LATAbits.LATA4 = 1; // RCK high
    short_pause();
    LATAbits.LATA4 = 0; // RCK low

    latch_pause();

    zero_sr();
}

inline void FaultCondition()
{
    int16_t i;

    if(fault_bits)
    {
        WriteRelays(fault_bits);
    }
    INTCONbits.GIE = 0;
    // cause WDT reset
    for(;;)
    {
        for(i = 0; i < 10000; i++);
        LATCbits.LATC3 = 0;
        for(i = 0; i < 10000; i++);
        LATCbits.LATC3 = 1;
    }
}

void ReceiveSetRelays(void)
{
    WriteRelays(SetupPkt.wValue);
}

void ReceiveSetFault(void)
{
    fault_bits = SetupPkt.wValue;
}

void ReceiveHeartbeat(void)
{
    if(SetupPkt.wValue == 0)
    {
        INTCONbits.TMR0IE = 0;
    }
    else
    {
        heartbeat_counter = SetupPkt.wValue;
        INTCONbits.TMR0IE = 1;
    }
}

void USBCBCheckOtherReq(void)
{
    if(SetupPkt.bmRequestType == VENDOR_READ)
    {
        switch(SetupPkt.bRequest)
        {
            case CTRL_READ_REG_8:
                Send_I2C_StartBit();                    // send start bit
                Send_I2C_Data((SetupPkt.wIndex << 1) | I2C_WRITE);    // send control byte with R/W bit set low
                Send_I2C_Data(SetupPkt.wValue);         // send word address

                Send_I2C_StartBit();                    // send start bit
                Send_I2C_Data((SetupPkt.wIndex << 1) | I2C_READ);     // send control byte with R/W bit set high
                CtrlTrfData[0] = Read_I2C_Data();       // now we read the data coming back
                Send_I2C_NAK();                         // send a the NAK to tell the IMU we don't want any more data
                Send_I2C_StopBit();                     // and then send the stop bit

                inPipes[0].pSrc.bRam = (BYTE*)&CtrlTrfData;         // Set Source
                inPipes[0].wCount.Val = 1;                         // Set data count
                inPipes[0].info.Val = USB_EP0_BUSY | USB_EP0_RAM;    // Set memory type
                break;

            case CTRL_READ_REG_16:
                Send_I2C_StartBit();                    // send start bit
                Send_I2C_Data((SetupPkt.wIndex << 1) | I2C_WRITE);    // send control byte with R/W bit set low
                Send_I2C_Data(SetupPkt.wValue);         // send word address

                Send_I2C_StartBit();                    // send start bit
                Send_I2C_Data((SetupPkt.wIndex << 1) | I2C_READ);     // send control byte with R/W bit set high
                CtrlTrfData[0] = Read_I2C_Data();       // now we read the data coming back
                Send_I2C_ACK();                         // send a the NAK to tell the IMU we don't want any more data
                CtrlTrfData[1] = Read_I2C_Data();       // now we read the data coming back
                Send_I2C_NAK();                         // send a the NAK to tell the IMU we don't want any more data
                Send_I2C_StopBit();                     // and then send the stop bit

                inPipes[0].pSrc.bRam = (BYTE*)&CtrlTrfData;         // Set Source
                inPipes[0].wCount.Val = 2;                         // Set data count
                inPipes[0].info.Val = USB_EP0_BUSY | USB_EP0_RAM;    // Set memory type
                break;
        }
    }
    else if(SetupPkt.bmRequestType == VENDOR_WRITE)
    {
        switch(SetupPkt.bRequest)
        {
            case CTRL_SET_LED:
                outPipes[0].pDst.bRam = (BYTE*)CtrlTrfData;
                outPipes[0].wCount.Val = 0;
                outPipes[0].pFunc = &SetLED;
                outPipes[0].info.bits.busy = 1;
                break;
            case CTRL_WRITE_REG_8: 
                outPipes[0].pDst.bRam = (BYTE*)CtrlTrfData;
                outPipes[0].wCount.Val = 1;
                outPipes[0].pFunc = &ReceiveCtrlWriteReg8;
                outPipes[0].info.bits.busy = 1;
                break;
            case CTRL_SET_RELAYS:
                outPipes[0].pDst.bRam = (BYTE*)CtrlTrfData;
                outPipes[0].wCount.Val = 0;
                outPipes[0].pFunc = &ReceiveSetRelays;
                outPipes[0].info.bits.busy = 1;
                break;
            case CTRL_SET_FAULT:
                outPipes[0].pDst.bRam = (BYTE*)CtrlTrfData;
                outPipes[0].wCount.Val = 0;
                outPipes[0].pFunc = &ReceiveSetFault;
                outPipes[0].info.bits.busy = 1;
                break;
            case CTRL_HEARTBEAT:
                outPipes[0].pDst.bRam = (BYTE*)CtrlTrfData;
                outPipes[0].wCount.Val = 0;
                outPipes[0].pFunc = &ReceiveHeartbeat;
                outPipes[0].info.bits.busy = 1;
                break;
        }
    }
}

void USBCBStdSetDscHandler(void)
{
}

void USBCBInitEP(void)
{
}

void USBCBSendResume(void)
{
}

BOOL USER_USB_CALLBACK_EVENT_HANDLER(int event, void *pdata, WORD size)
{
    switch( event )
    {
        case EVENT_TRANSFER:
            //Add application specific callback task or callback function here if desired.
            break;
        case EVENT_SOF:
            USBCB_SOF_Handler();
            break;
        case EVENT_SUSPEND:
            USBCBSuspend();
            break;
        case EVENT_RESUME:
            USBCBWakeFromSuspend();
            break;
        case EVENT_CONFIGURED:
            USBCBInitEP();
            break;
        case EVENT_SET_DESCRIPTOR:
            USBCBStdSetDscHandler();
            break;
        case EVENT_EP0_REQUEST:
            USBCBCheckOtherReq();
            break;
        case EVENT_BUS_ERROR:
            USBCBErrorHandler();
            break;
        case EVENT_TRANSFER_TERMINATED:
            //Add application specific callback task or callback function here if desired.
            //The EVENT_TRANSFER_TERMINATED event occurs when the host performs a CLEAR
            //FEATURE (endpoint halt) request on an application endpoint which was
            //previously armed (UOWN was = 1).  Here would be a good place to:
            //1.  Determine which endpoint the transaction that just got terminated was
            //      on, by checking the handle value in the *pdata.
            //2.  Re-arm the endpoint if desired (typically would be the case for OUT
            //      endpoints).
            break;
        default:
            break;
    }
    return TRUE;
}

// *****************************************************************************
// ************** USB Class Specific Callback Function(s) **********************
// *****************************************************************************

//Secondary callback function that gets called when the above
//control transfer completes for the USBHIDCBSetReportHandler()
//void USBHIDCBSetReportComplete(void)
//{
//    ReceivedData((BYTE*)&CtrlTrfData);
//}

//void USBHIDCBSetReportHandler(void)
//{
//	//Prepare to receive the keyboard LED state data through a SET_REPORT
//	//control transfer on endpoint 0.  The host should only send 1 byte,
//	//since this is all that the report descriptor allows it to send.
//
//	USBEP0Receive((BYTE*)&CtrlTrfData, USB_EP0_BUFF_SIZE, USBHIDCBSetReportComplete);
//}
