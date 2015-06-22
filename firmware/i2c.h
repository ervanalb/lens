/* 
 * File:   i2c.h
 * Author: Eric
 *
 * Created on June 16, 2014, 6:15 AM
 */

#ifndef I2C_H
#define	I2C_H

#ifdef	__cplusplus
extern "C" {
#endif

#define I2C_READ 1
#define I2C_WRITE 0

inline void Init_I2C(void);
inline void Send_I2C_Data(unsigned char databyte);
inline unsigned char Read_I2C_Data(void);
inline void Send_I2C_StartBit(void);
inline void Send_I2C_StopBit(void);
inline void Send_I2C_ACK(void);
inline void Send_I2C_NAK(void);


#ifdef	__cplusplus
}
#endif

#endif	/* I2C_H */

