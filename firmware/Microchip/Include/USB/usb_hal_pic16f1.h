/******************************************************************************

    USB Hardware Abstraction Layer (HAL)  (Header File)

Summary:
    This file abstracts the hardware interface.  The USB stack firmware can be
    compiled to work on different USB microcontrollers, such as PIC18 and PIC24.
    The USB related special function registers and bit names are generally very
    similar between the device families, but small differences in naming exist.

Description:
    This file abstracts the hardware interface.  The USB stack firmware can be
    compiled to work on different USB microcontrollers, such as PIC18 and PIC24.
    The USB related special function registers and bit names are generally very
    similar between the device families, but small differences in naming exist.
    
    In order to make the same set of firmware work accross the device families,
    when modifying SFR contents, a slightly abstracted name is used, which is
    then "mapped" to the appropriate real name in the usb_hal_picxx.h header.
    
    Make sure to include the correct version of the usb_hal_picxx.h file for 
    the microcontroller family which will be used.

    This file is located in the "\<Install Directory\>\\Microchip\\Include\\USB"
    directory.
    
    When including this file in a new project, this file can either be
    referenced from the directory in which it was installed or copied
    directly into the user application folder. If the first method is
    chosen to keep the file located in the folder in which it is installed
    then include paths need to be added so that the library and the
    application both know where to reference each others files. If the
    application folder is located in the same folder as the Microchip
    folder (like the current demo folders), then the following include
    paths need to be added to the application's project:
    
    .

    ..\\..\\MicrochipInclude
        
    If a different directory structure is used, modify the paths as
    required. An example using absolute paths instead of relative paths
    would be the following:
    
    C:\\Microchip Solutions\\Microchip\\Include
    
    C:\\Microchip Solutions\\My Demo Application 

*******************************************************************************/
//DOM-IGNORE-BEGIN
/******************************************************************************

 File Description:

 This file defines the interface to the USB hardware abstraction layer.

 * Filename:    usb_hal_pic16f1.h
 Dependencies:	See INCLUDES section
 Processor:		Use this header file when using this firmware with PIC16 USB
 				microcontrollers
 Hardware:		
 Complier:  	Microchip XC8
 Company:		Microchip Technology, Inc.

 Software License Agreement:

 The software supplied herewith by Microchip Technology Incorporated
 (the "Company") for its PIC(R) Microcontroller is intended and
 supplied to you, the Company's customer, for use solely and
 exclusively on Microchip PIC Microcontroller products. The
 software is owned by the Company and/or its supplier, and is
 protected under applicable copyright laws. All rights are reserved.
 Any use in violation of the foregoing restrictions may subject the
 user to criminal sanctions under applicable laws, as well as to
 civil liability for the breach of the terms and conditions of this
 license.

 THIS SOFTWARE IS PROVIDED IN AN "AS IS" CONDITION. NO WARRANTIES,
 WHETHER EXPRESS, IMPLIED OR STATUTORY, INCLUDING, BUT NOT LIMITED
 TO, IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A
 PARTICULAR PURPOSE APPLY TO THIS SOFTWARE. THE COMPANY SHALL NOT,
 IN ANY CIRCUMSTANCES, BE LIABLE FOR SPECIAL, INCIDENTAL OR
 CONSEQUENTIAL DAMAGES, FOR ANY REASON WHATSOEVER.

 *************************************************************************/
#ifndef USB_HAL_PIC16_H
#define USB_HAL_PIC16_H

/*****************************************************************************/
/****** include files ********************************************************/
/*****************************************************************************/

#include "Compiler.h"
#include "usb_config.h"

/*****************************************************************************/
/****** Constant definitions *************************************************/
/*****************************************************************************/

//----- USBEnableEndpoint() input defintions ----------------------------------
#define USB_HANDSHAKE_ENABLED   0x10
#define USB_HANDSHAKE_DISABLED  0x00

#define USB_OUT_ENABLED         0x04
#define USB_OUT_DISABLED        0x00

#define USB_IN_ENABLED          0x02
#define USB_IN_DISABLED         0x00

#define USB_ALLOW_SETUP         0x00
#define USB_DISALLOW_SETUP      0x08

#define USB_STALL_ENDPOINT      0x01

//----- usb_config.h input defintions -----------------------------------------
#define USB_PULLUP_ENABLE 0x10
#define USB_PULLUP_DISABLED 0x00

#define USB_INTERNAL_TRANSCEIVER 0x00
#define USB_EXTERNAL_TRANSCEIVER 0x08

#define USB_FULL_SPEED 0x04
#define USB_LOW_SPEED  0x00

//----- Interrupt Flag definitions --------------------------------------------
#define USBTransactionCompleteIE UIEbits.TRNIE
#define USBTransactionCompleteIF UIRbits.TRNIF
#define USBTransactionCompleteIFReg UIR
#define USBTransactionCompleteIFBitNum 0xF7		//AND mask for clearing TRNIF bit position 3

#define USBResetIE  UIEbits.URSTIE
#define USBResetIF  UIRbits.URSTIF
#define USBResetIFReg UIR
#define USBResetIFBitNum 0xFE					//AND mask for clearing URSTIF bit position 0

#define USBIdleIE UIEbits.IDLEIE
#define USBIdleIF UIRbits.IDLEIF
#define USBIdleIFReg UIR
#define USBIdleIFBitNum 0xEF					//AND mask for clearing IDLEIF bit position 5

#define USBActivityIE UIEbits.ACTVIE
#define USBActivityIF UIRbits.ACTVIF
#define USBActivityIFReg UIR
#define USBActivityIFBitNum 0xFB				//AND mask for clearing ACTVIF bit position 2

#define USBSOFIE UIEbits.SOFIE
#define USBSOFIF UIRbits.SOFIF
#define USBSOFIFReg UIR
#define USBSOFIFBitNum 0xBF						//AND mask for clearing SOFIF bit position 6

#define USBStallIE UIEbits.STALLIE
#define USBStallIF UIRbits.STALLIF
#define USBStallIFReg UIR
#define USBStallIFBitNum 0xDF					//AND mask for clearing STALLIF bit position 5

#define USBErrorIE UIEbits.UERRIE
#define USBErrorIF UIRbits.UERRIF
#define USBErrorIFReg UIR
#define USBErrorIFBitNum 0xFD					//UERRIF bit position 1.  Note: This bit is read only and is cleared by clearing the enabled UEIR flags

//----- Event call back defintions --------------------------------------------
#if defined(USB_DISABLE_SOF_HANDLER)
    #define USB_SOF_INTERRUPT 0x00
#else
    #define USB_SOF_INTERRUPT 0x40
#endif

#if defined(USB_DISABLE_ERROR_HANDLER)
    #define USB_ERROR_INTERRUPT 0x02
#else
    #define USB_ERROR_INTERRUPT 0x02
#endif

//----- USB module control bits -----------------------------------------------
#define USBPingPongBufferReset UCONbits.PPBRST
#define USBSE0Event UCONbits.SE0
#define USBSuspendControl UCONbits.SUSPND
#define USBPacketDisable UCONbits.PKTDIS
#define USBResumeControl UCONbits.RESUME

//----- BDnSTAT bit definitions -----------------------------------------------
#define _BSTALL     0x04        //Buffer Stall enable
#define _DTSEN      0x08        //Data Toggle Synch enable
#define _INCDIS     0x10        //Address increment disable
#define _KEN        0x20        //SIE keeps buff descriptors enable
#define _DAT0       0x00        //DATA0 packet expected next
#define _DAT1       0x40        //DATA1 packet expected next
#define _DTSMASK    0x40        //DTS Mask
#define _USIE       0x80        //SIE owns buffer
#define _UCPU       0x00        //CPU owns buffer
#define _STAT_MASK  0xFF

#define USTAT_EP0_PP_MASK   ~0x02
#define USTAT_EP_MASK       0x7E
#define USTAT_EP0_OUT       0x00
#define USTAT_EP0_OUT_EVEN  0x00
#define USTAT_EP0_OUT_ODD   0x02
#define USTAT_EP0_IN        0x04
#define USTAT_EP0_IN_EVEN   0x04
#define USTAT_EP0_IN_ODD    0x06

#define ENDPOINT_MASK 0b01111000

//----- U1EP bit definitions --------------------------------------------------
#define UEP_STALL 0x0001
// Cfg Control pipe for this ep
/* Endpoint configuration options for USBEnableEndpoint() function */
#define EP_CTRL     0x06            // Cfg Control pipe for this ep
#define EP_OUT      0x0C            // Cfg OUT only pipe for this ep
#define EP_IN       0x0A            // Cfg IN only pipe for this ep
#define EP_OUT_IN   0x0E            // Cfg both OUT & IN pipes for this ep

//----- Remap the PIC18 register name space------------------------------------
#define U1ADDR UADDR
#define U1IE UIE
#define U1IR UIR
#define U1EIR UEIR
#define U1EIE UEIE
#define U1CON UCON

#if (__XC8_VERSION == 1000)
#define U1EP0 UEP7
#define U1EP0bits UEP7bits
#else
#define U1EP0 UEP0
#define U1EP0bits UEP0bits
#endif

#define U1CONbits UCONbits
#define U1EP1 UEP1
#define U1CNFG1 UCFG
#define U1STAT USTAT


//----- Defintions for BDT address --------------------------------------------
#define BDT_BASE_ADDR   0x2000
#define BDT_BASE_ADDR_TAG @ BDT_BASE_ADDR
#define BDT_ENTRY_SIZE 4

#define CTRL_TRF_SETUP_ADDR     BDT_BASE_ADDR + (BDT_ENTRY_SIZE * BDT_NUM_ENTRIES)
#define CTRL_TRF_DATA_ADDR      CTRL_TRF_SETUP_ADDR + USB_EP0_BUFF_SIZE

#define CTRL_TRF_SETUP_ADDR_TAG @ CTRL_TRF_SETUP_ADDR
#define CTRL_TRF_DATA_ADDR_TAG  @ CTRL_TRF_DATA_ADDR

//----- Depricated defintions - will be removed at some point of time----------
//--------- Depricated in v2.2
#define _LS         0x00            // Use Low-Speed USB Mode
#define _FS         0x04            // Use Full-Speed USB Mode
#define _TRINT      0x00            // Use internal transceiver
#define _TREXT      0x08            // Use external transceiver
#define _PUEN       0x10            // Use internal pull-up resistor
#define _OEMON      0x40            // Use SIE output indicator

/*****************************************************************************/
/****** Type definitions *****************************************************/
/*****************************************************************************/

// Buffer Descriptor Status Register layout.
typedef union _BD_STAT
{
    BYTE Val;
    struct{
        //If the CPU owns the buffer then these are the values
        unsigned BC8:1;         //bit 8 of the byte count
        unsigned BC9:1;         //bit 9 of the byte count
        unsigned BSTALL:1;      //Buffer Stall Enable
        unsigned DTSEN:1;       //Data Toggle Synch Enable
        unsigned INCDIS:1;      //Address Increment Disable
        unsigned KEN:1;         //BD Keep Enable
        unsigned DTS:1;         //Data Toggle Synch Value
        unsigned UOWN:1;        //USB Ownership
    };
    struct{
        //if the USB module owns the buffer then these are
        // the values
        unsigned :2;
        unsigned PID0:1;        //Packet Identifier
        unsigned PID1:1;
        unsigned PID2:1;
        unsigned PID3:1;
        unsigned :1;
    };
    struct{
        unsigned :2;
        unsigned PID:4;         //Packet Identifier
        unsigned :2;
    };
} BD_STAT;                      //Buffer Descriptor Status Register

// BDT Entry Layout
typedef union __BDT
{
    struct
    {
        BD_STAT STAT;
        BYTE CNT;
        BYTE ADRL;                      //Buffer Address Low
        BYTE ADRH;                      //Buffer Address High
    };
    struct
    {
        unsigned filler1:8;
        unsigned filler2:8;
        WORD     ADR;                      //Buffer Address
    };
    DWORD Val;
    BYTE v[4];
} BDT_ENTRY;

// USTAT Register Layout
typedef union __USTAT
{
    struct
    {
        unsigned char filler1:1;
        unsigned char ping_pong:1;
        unsigned char direction:1;
        unsigned char endpoint_number:4;
    };
    BYTE Val;
} USTAT_FIELDS;

//Macros for fetching parameters from a USTAT_FIELDS variable.
#define USBHALGetLastEndpoint(stat)     stat.endpoint_number
#define USBHALGetLastDirection(stat)    stat.direction
#define USBHALGetLastPingPong(stat)     stat.ping_pong


typedef union _POINTER
{
    struct
    {
        BYTE bLow;
        BYTE bHigh;
        //byte bUpper;
    };
    WORD _word;                         // bLow & bHigh
    
    //pFunc _pFunc;                       // Usage: ptr.pFunc(); Init: ptr.pFunc = &<Function>;

    BYTE* bRam;                         // Ram byte pointer: 2 bytes pointer pointing
                                        // to 1 byte of data
    WORD* wRam;                         // Ram word poitner: 2 bytes poitner pointing
                                        // to 2 bytes of data

    ROM BYTE* bRom;                     // Size depends on compiler setting
    ROM WORD* wRom;
    //rom near byte* nbRom;               // Near = 2 bytes pointer
    //rom near word* nwRom;
    //rom far byte* fbRom;                // Far = 3 bytes pointer
    //rom far word* fwRom;
} POINTER;

/*****************************************************************************/
/****** Function prototypes and macro functions ******************************/
/*****************************************************************************/

#define ConvertToPhysicalAddress(a) (((WORD)(a))& 0x7FFF)
#define ConvertToVirtualAddress(a)  ((void *)(a))
#define USBClearUSBInterrupt() PIR2bits.USBIF = 0;
#if defined(USB_INTERRUPT)
    #define USBMaskInterrupts() {PIE2bits.USBIE = 0;}
    #define USBUnmaskInterrupts() {PIE2bits.USBIE = 1;}
#else
    #define USBMaskInterrupts() 
    #define USBUnmaskInterrupts() 
#endif

#define USBInterruptFlag PIR2bits.USBIF

//STALLIE, IDLEIE, TRNIE, and URSTIE are all enabled by default and are required
#if defined(USB_INTERRUPT)
    #define USBEnableInterrupts() {PIE2bits.USBIE = 1;INTCONbits.PEIE = 1; INTCONbits.GIE = 1;}
#else
    #define USBEnableInterrupts()
#endif

#define USBDisableInterrupts() {PIE2bits.USBIE = 0;}

#define SetConfigurationOptions()   {\
                                        U1CNFG1 = USB_PULLUP_OPTION | USB_TRANSCEIVER_OPTION | USB_SPEED_OPTION | USB_PING_PONG_MODE;\
                                        U1EIE = 0x9F;\
                                        UIE = 0x39 | USB_SOF_INTERRUPT | USB_ERROR_INTERRUPT;\
                                    }  

/****************************************************************
    Function:
        void USBPowerModule(void)
        
    Description:
        This macro is used to power up the USB module if required<br>
        PIC18: defines as nothing<br>
        PIC24: defines as U1PWRCbits.USBPWR = 1;<br>
        
    Parameters:
        None
        
    Return Values:
        None
        
    Remarks:
        None
        
  ****************************************************************/
#define USBPowerModule()

/****************************************************************
    Function:
        void USBModuleDisable(void)
        
    Description:
        This macro is used to disable the USB module
        
    Parameters:
        None
        
    Return Values:
        None
        
    Remarks:
        None
        
  ****************************************************************/
#define USBModuleDisable() {\
    UCON = 0;\
    UIE = 0;\
    USBDeviceState = DETACHED_STATE;\
}    

/****************************************************************
    Function:
        USBSetBDTAddress(addr)
        
    Description:
        This macro is used to power up the USB module if required
        
    Parameters:
        None
        
    Return Values:
        None
        
    Remarks:
        None
        
  ****************************************************************/
#define USBSetBDTAddress(addr)

/********************************************************************
 * Function (macro): void USBClearInterruptFlag(register, BYTE if_and_flag_mask)
 *
 * PreCondition:    None
 *
 * Input:           
 *   register - the register mnemonic for the register holding the interrupt 
 				flag to be cleared
 *   BYTE if_and_flag_mask - an AND mask for the interrupt flag that will be 
 				cleared
 *
 * Output:          None
 *
 * Side Effects:    None
 *
 * Overview:        Clears the specified USB interrupt flag.
 *
 * Note:            
 *******************************************************************/
#define USBClearInterruptFlag(reg_name, if_and_flag_mask)	(reg_name &= if_and_flag_mask)	

/********************************************************************
    Function:
        void USBClearInterruptRegister(WORD reg)
        
    Summary:
        Clears the specified interrupt register
        
    PreCondition:
        None
        
    Parameters:
        WORD reg - the register name that needs to be cleared
        
    Return Values:
        None
        
    Remarks:
        None
 
 *******************************************************************/
#define USBClearInterruptRegister(reg) reg = 0;

/********************************************************************
    Function:
        void DisableNonZeroEndpoints(UINT8 last_ep_num)
        
    Summary:
        Clears the control registers for the specified non-zero endpoints
        
    PreCondition:
        None
        
    Parameters:
        UINT8 last_ep_num - the last endpoint number to clear.  This
        number should include all endpoints used in any configuration.
        
    Return Values:
        None
        
    Remarks:
        None
  *******************************************************************/
#if (__XC8_VERSION == 1000)
#define DisableNonZeroEndpoints(last_ep_num)        \
    {                                               \
        BYTE i;                                     \
        BYTE* p = (BYTE*)&UEP6;                     \
        for(i=0;i<last_ep_num;i++)                  \
            *p++ = 0;                               \
    }
#else
#define DisableNonZeroEndpoints(last_ep_num)        \
    {                                               \
        BYTE i;                                     \
        BYTE* p = (BYTE*)&UEP1;                     \
        for(i=0;i<last_ep_num;i++)                  \
            *p++ = 0;                               \
    }
#endif


//memset((void*)&UEP1,(int)0x00,(size_t)(last_ep_num));

/*****************************************************************************/
/****** Compiler checks ******************************************************/
/*****************************************************************************/

//Definitions for the BDT
#ifndef USB_PING_PONG_MODE
    #error "No ping pong mode defined."
#endif

/*****************************************************************************/
/****** Extern variable definitions ******************************************/
/*****************************************************************************/

#if !defined(USBDEVICE_C)
    //extern USB_VOLATILE USB_DEVICE_STATE USBDeviceState;
    extern USB_VOLATILE BYTE USBActiveConfiguration;
    extern USB_VOLATILE IN_PIPE inPipes[1];
    extern USB_VOLATILE OUT_PIPE outPipes[1];
#endif

extern volatile BDT_ENTRY* pBDTEntryOut[USB_MAX_EP_NUMBER+1];
extern volatile BDT_ENTRY* pBDTEntryIn[USB_MAX_EP_NUMBER+1];

#endif //#ifndef USB_HAL_PIC18_H
