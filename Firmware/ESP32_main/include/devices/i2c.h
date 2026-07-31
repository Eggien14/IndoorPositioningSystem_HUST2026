#ifndef I2C_H
#define I2C_H

#include "config.h"

int16_t read_16_bit_LSB_MSB(uint8_t reg, uint8_t device_address);

#endif // I2C_H