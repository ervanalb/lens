#include "i2c.h"
#include "Compiler.h"

inline void Init_I2C(void)
{
    TRISCbits.TRISC0 = 1;
    TRISCbits.TRISC1 = 1;

    ANSELC = 0;

    SSPCON1bits.SSPM=0x08;       // I2C Master mode, clock = Fosc/16
    SSPCON1bits.SSPEN=1;         // enable MSSP port
    SSPADD = 29;
}

//**************************************************************************************
// Send one byte to SEE
//**************************************************************************************
inline void Send_I2C_Data(unsigned char databyte)
{
    PIR1bits.SSP1IF=0;          // clear SSP interrupt bit
    SSPBUF = databyte;          // send databyte
    while(!PIR1bits.SSP1IF);    // Wait for interrupt flag to go high indicating transmission is complete
}

//**************************************************************************************
// Read one byte from SEE
//**************************************************************************************
inline unsigned char Read_I2C_Data(void)
{
    PIR1bits.SSP1IF=0;          // clear SSP interrupt bit
    SSPCON2bits.RCEN=1;         // set the receive enable bit to initiate a read of 8 bits from the serial eeprom
    while(!PIR1bits.SSP1IF);    // Wait for interrupt flag to go high indicating transmission is complete
    return (SSPBUF);            // Data from eeprom is now in the SSPBUF so return that value
}

//**************************************************************************************
// Send start bit to SEE
//**************************************************************************************
inline void Send_I2C_StartBit(void)
{
    PIR1bits.SSP1IF=0;          // clear SSP interrupt bit
    SSPCON2bits.SEN=1;          // send start bit
    while(!PIR1bits.SSP1IF);    // Wait for the SSPIF bit to go back high before we load the data buffer
}

//**************************************************************************************
// Send stop bit to SEE
//**************************************************************************************
inline void Send_I2C_StopBit(void)
{
    PIR1bits.SSP1IF=0;          // clear SSP interrupt bit
    SSPCON2bits.PEN=1;          // send stop bit
    while(!PIR1bits.SSP1IF);    // Wait for interrupt flag to go high indicating transmission is complete
}


//**************************************************************************************
// Send ACK bit to SEE
//**************************************************************************************
inline void Send_I2C_ACK(void)
{
   PIR1bits.SSP1IF=0;          // clear SSP interrupt bit
   SSPCON2bits.ACKDT=0;        // clear the Acknowledge Data Bit - this means we are sending an Acknowledge or 'ACK'
   SSPCON2bits.ACKEN=1;        // set the ACK enable bit to initiate transmission of the ACK bit to the serial eeprom
   while(!PIR1bits.SSP1IF);    // Wait for interrupt flag to go high indicating transmission is complete
}

//**************************************************************************************
// Send NAK bit to SEE
//**************************************************************************************
inline void Send_I2C_NAK(void)
{
    PIR1bits.SSP1IF=0;           // clear SSP interrupt bit
    SSPCON2bits.ACKDT=1;        // set the Acknowledge Data Bit- this means we are sending a No-Ack or 'NAK'
    SSPCON2bits.ACKEN=1;        // set the ACK enable bit to initiate transmission of the ACK bit to the serial eeprom
    while(!PIR1bits.SSP1IF);    // Wait for interrupt flag to go high indicating transmission is complete
}
