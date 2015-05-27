/*******************************************************************************
  File Information:
    FileName:     	usb_function_hid.h
    Dependencies:   See INCLUDES section
    Processor:      Microchip USB Microcontrollers
    Hardware:       The code is natively intended to be used on the following
    				hardware platforms: PICDEM FS USB Demo Board, 
    				PIC18F87J50 FS USB Plug-In Module, or
    				Explorer 16 + PIC24 USB PIM.  The firmware may be
    				modified for use on other USB platforms by editing the
    				HardwareProfile.h file.
    Complier:  	    Microchip C18, C30, C32
    Company:        Microchip Technology, Inc.
    
    Software License Agreement:
    
    The software supplied herewith by Microchip Technology Incorporated
    (the “Company”) for its PIC® Microcontroller is intended and
    supplied to you, the Company’s customer, for use solely and
    exclusively on Microchip PIC Microcontroller products. The
    software is owned by the Company and/or its supplier, and is
    protected under applicable copyright laws. All rights are reserved.
    Any use in violation of the foregoing restrictions may subject the
    user to criminal sanctions under applicable laws, as well as to
    civil liability for the breach of the terms and conditions of this
    license.
    
    THIS SOFTWARE IS PROVIDED IN AN “AS IS” CONDITION. NO WARRANTIES,
    WHETHER EXPRESS, IMPLIED OR STATUTORY, INCLUDING, BUT NOT LIMITED
    TO, IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A
    PARTICULAR PURPOSE APPLY TO THIS SOFTWARE. THE COMPANY SHALL NOT,
    IN ANY CIRCUMSTANCES, BE LIABLE FOR SPECIAL, INCIDENTAL OR
    CONSEQUENTIAL DAMAGES, FOR ANY REASON WHATSOEVER.

  File Description:
    
    Change History:
     Rev   Date         Description
     1.0   11/19/2004   Initial release
     2.1   02/26/2007   Updated for simplicity and to use common
                        coding style

  Summary:
    This file contains all of functions, macros, definitions, variables,
    datatypes, etc. that are required for usage with the HID function
    driver. This file should be included in projects that use the HID
    \function driver.  This file should also be included into the 
    usb_descriptors.c file and any other user file that requires access to the
    HID interface.
    
    
    
    This file is located in the "\<Install Directory\>\\Microchip\\Include\\USB"
    directory.

  Description:
    USB HID Function Driver File
    
    This file contains all of functions, macros, definitions, variables,
    datatypes, etc. that are required for usage with the HID function
    driver. This file should be included in projects that use the HID
    \function driver.  This file should also be included into the 
    usb_descriptors.c file and any other user file that requires access to the
    HID interface.
    
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
    
    ..\\..\\Microchip\\Include
    .
    
    If a different directory structure is used, modify the paths as
    required. An example using absolute paths instead of relative paths
    would be the following:
    
    C:\\Microchip Solutions\\Microchip\\Include
    
    C:\\Microchip Solutions\\My Demo Application 


 Change History:
   Rev    Description
   ----   ------------------------------------------
   1.0    Initial release
   2.1    Updated for simplicity and to use common
          coding style
   2.6    Minor changes in defintions

*******************************************************************/
#ifndef HID_H
#define HID_H
//DOM-IGNORE-END

/** INCLUDES *******************************************************/

/** DEFINITIONS ****************************************************/

/* Class-Specific Requests */
#define GET_REPORT      0x01
#define GET_IDLE        0x02
#define GET_PROTOCOL    0x03
#define SET_REPORT      0x09
#define SET_IDLE        0x0A
#define SET_PROTOCOL    0x0B

/* Class Descriptor Types */
#define DSC_HID         0x21
#define DSC_RPT         0x22
#define DSC_PHY         0x23

/* Protocol Selection */
#define BOOT_PROTOCOL   0x00
#define RPT_PROTOCOL    0x01

/* HID Interface Class Code */
#define HID_INTF                    0x03

/* HID Interface Class SubClass Codes */
#define NO_INTF_SUBCLASS            0x00
#define BOOT_INTF_SUBCLASS          0x01

/* HID Interface Class Protocol Codes */
#define HID_PROTOCOL_NONE           0x00
#define HID_PROTOCOL_KEYBOARD       0x01
#define HID_PROTOCOL_MOUSE          0x02

/********************************************************************
	Function:
		void USBCheckHIDRequest(void)

 	Summary:
 		This routine handles HID specific request that happen on EP0.
        This function should be called from the USBCBCheckOtherReq() call back
        function whenever implementing a HID device.

 	Description:
 		This routine handles HID specific request that happen on EP0.  These
        include, but are not limited to, requests for the HID report
        descriptors.  This function should be called from the
        USBCBCheckOtherReq() call back function whenever using an HID device.

        Typical Usage:
        <code>
        void USBCBCheckOtherReq(void)
        {
            //Since the stack didn't handle the request I need to check
            //  my class drivers to see if it is for them
            USBCheckHIDRequest();
        }
        </code>

	PreCondition:
		None

	Parameters:
		None

	Return Values:
		None

	Remarks:
		None

 *******************************************************************/
void USBCheckHIDRequest(void);

/********************************************************************
    Function:
        BOOL HIDTxHandleBusy(USB_HANDLE handle)
        
    Summary:
        Retreives the status of the buffer ownership

    Description:
        Retreives the status of the buffer ownership.  This function will
        indicate if the previous transfer is complete or not.
        
        This function will take the input handle (pointer to a BDT entry) and 
        will check the UOWN bit.  If the UOWN bit is set then that indicates 
        that the transfer is not complete and the USB module still owns the data
        memory.  If the UOWN bit is clear that means that the transfer is 
        complete and that the CPU now owns the data memory.  

        For more information about the BDT, please refer to the appropriate 
        datasheet for the device in use.
        
        Typical Usage:
        <code>
        //make sure that the last transfer isn't busy by checking the handle
        if(!HIDTxHandleBusy(USBInHandle))
        {
            //Send the data contained in the ToSendDataBuffer[] array out on
            //  endpoint HID_EP
            USBInHandle = HIDTxPacket(HID_EP,(BYTE*)&ToSendDataBuffer[0],sizeof(ToSendDataBuffer));
        }
        </code>

    PreCondition:
        None.
        
    Parameters:
        USB_HANDLE handle - the handle for the transfer in question.
        The handle is returned by the HIDTxPacket() and HIDRxPacket()
        functions.  Please insure that USB_HANDLE objects are initialized
        to NULL.
        
    Return Values:
        TRUE - the HID handle is still busy
        FALSE - the HID handle is not busy and is ready to send
                additional data.
        
   Remarks:
        None
 
 *******************************************************************/
#define HIDTxHandleBusy(handle) USBHandleBusy(handle)

/********************************************************************
    Function:
        BOOL HIDRxHandleBusy(USB_HANDLE handle)
        
    Summary:
        Retreives the status of the buffer ownership
        
    Description:
        Retreives the status of the buffer ownership.  This function will
        indicate if the previous transfer is complete or not.
        
        This function will take the input handle (pointer to a BDT entry) and 
        will check the UOWN bit.  If the UOWN bit is set then that indicates 
        that the transfer is not complete and the USB module still owns the data
        memory.  If the UOWN bit is clear that means that the transfer is 
        complete and that the CPU now owns the data memory.  

        For more information about the BDT, please refer to the appropriate 
        datasheet for the device in use.

        Typical Usage:
        <code>
        if(!HIDRxHandleBusy(USBOutHandle))
        {
            //The data is available in the buffer that was specified when the
            //  HIDRxPacket() was called.
        }
        </code>

    PreCondition:
        None
        
    Parameters:
        USB_HANDLE handle - the handle for the transfer in question.
        The handle is returned by the HIDTxPacket() and HIDRxPacket()
        functions.  Please insure that USB_HANDLE objects are initialized
        to NULL.
        
    Return Values:
        TRUE - the HID handle is still busy
        FALSE - the HID handle is not busy and is ready to receive
                additional data.
        
   Remarks:
        None
 
 *******************************************************************/
#define HIDRxHandleBusy(handle) USBHandleBusy(handle)

/********************************************************************
    Function:
        USB_HANDLE HIDTxPacket(BYTE ep, BYTE* data, WORD len)
        
    Summary:
        Sends the specified data out the specified endpoint

    Description:
        This function sends the specified data out the specified 
        endpoint and returns a handle to the transfer information.

        Typical Usage:
        <code>
        //make sure that the last transfer isn't busy by checking the handle
        if(!HIDTxHandleBusy(USBInHandle))
        {
            //Send the data contained in the ToSendDataBuffer[] array out on
            //  endpoint HID_EP
            USBInHandle = HIDTxPacket(HID_EP,(BYTE*)&ToSendDataBuffer[0],sizeof(ToSendDataBuffer));
        }
        </code>
        
    PreCondition:
        None
        
    Parameters:
        BYTE ep    - the endpoint you want to send the data out of
        BYTE* data - pointer to the data that you wish to send
        WORD len   - the length of the data that you wish to send
        
    Return Values:
        USB_HANDLE - a handle for the transfer.  This information
        should be kept to track the status of the transfer
        
    Remarks:
        None
  
 *******************************************************************/
#define HIDTxPacket USBTxOnePacket

/********************************************************************
    Function:
        USB_HANDLE HIDRxPacket(BYTE ep, BYTE* data, WORD len)
        
    Summary:
        Receives the specified data out the specified endpoint
        
    Description:
        Receives the specified data out the specified endpoint.

        Typical Usage:
        <code>
        //Read 64-bytes from endpoint HID_EP, into the ReceivedDataBuffer array.
        //  Make sure to save the return handle so that we can check it later
        //  to determine when the transfer is complete.
        USBOutHandle = HIDRxPacket(HID_EP,(BYTE*)&ReceivedDataBuffer,64);
        </code>

    PreCondition:
        None
        
    Parameters:
        BYTE ep    - the endpoint you want to receive the data into
        BYTE* data - pointer to where the data will go when it arrives
        WORD len   - the length of the data that you wish to receive
        
    Return Values:
        USB_HANDLE - a handle for the transfer.  This information
        should be kept to track the status of the transfer
        
    Remarks:
        None
  
 *******************************************************************/
#define HIDRxPacket USBRxOnePacket

// Section: STRUCTURES *********************************************/

//USB HID Descriptor header as detailed in section 
//"6.2.1 HID Descriptor" of the HID class definition specification
typedef struct _USB_HID_DSC_HEADER
{
    BYTE bDescriptorType;	//offset 9
    WORD wDscLength;		//offset 10
} USB_HID_DSC_HEADER;

//USB HID Descriptor header as detailed in section 
//"6.2.1 HID Descriptor" of the HID class definition specification
typedef struct _USB_HID_DSC
{
    BYTE bLength;			//offset 0 
	BYTE bDescriptorType;	//offset 1
	WORD bcdHID;			//offset 2
    BYTE bCountryCode;		//offset 4
	BYTE bNumDsc;			//offset 5


    //USB_HID_DSC_HEADER hid_dsc_header[HID_NUM_OF_DSC];
    /* HID_NUM_OF_DSC is defined in usbcfg.h */
    
} USB_HID_DSC;

/** Section: EXTERNS ********************************************************/
extern volatile CTRL_TRF_SETUP SetupPkt;
extern ROM BYTE configDescriptor1[];
extern volatile BYTE CtrlTrfData[USB_EP0_BUFF_SIZE];

#endif //HID_H
