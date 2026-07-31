#ifndef READ_VALVE_H
#define READ_VALVE_H

#include "config.h"

/**
 * @brief Read the valve opening percentage from the potentiometer
 *
 * This function reads the analog value from VALVE_PIN and converts
 * it into the valve opening percentage in the range of 0 to 100%.
 *
 * The maximum analog value corresponding to fully open valve is 700.
 *
 * @param valve_open_status Pointer to store the valve opening percentage
 */
void init_valve(void);
void read_valve(Valve_Data *valve_data);

#endif