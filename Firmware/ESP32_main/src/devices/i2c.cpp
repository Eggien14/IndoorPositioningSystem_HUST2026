#include "devices/i2c.h"

int16_t read_16_bit_LSB_MSB(uint8_t reg, uint8_t device_address)
{
    // Start I2C transmission with the specified device
    Wire.beginTransmission(device_address);
    // Send the register address we want to read from
    Wire.write(reg);
    // End transmission but keep connection active (false parameter)
    Wire.endTransmission(false);
    // Request 2 bytes from the specified register
    Wire.requestFrom((uint8_t)device_address, (uint8_t)2);
    // Read LSB (Least Significant Byte) first - lower 8 bits
    int16_t value = Wire.read();
    // Read MSB (Most Significant Byte) and shift left by 8 bits
    // Then combine with LSB using OR operation
    value |= (Wire.read() << 8);
    // Return the combined 16-bit value
    return value;
}