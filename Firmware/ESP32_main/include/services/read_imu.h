#ifndef READ_IMU_H
#define READ_IMU_H

#include "config.h"
#include "devices/i2c.h"

// Function initialization
/*#############################################################################################################*/
void init_IMU(void);

// Function to read IMU data
void read_IMU_data(IMU_Data *imu_data, uint8_t device_address);

#endif // READ_IMU_H    