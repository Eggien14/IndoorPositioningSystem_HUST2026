#ifndef UART_H
#define UART_H

// Libraries
#include "config.h"

// Function declarations

/*#############################################################################################################*/
/**
 * @brief Read WiFi_RSSI and BLE_RSSI values from 2 ESP32 via UART
 * @param uart Reference to HardwareSerial object for UART communication
 * @param rssi_data Pointer to array of RSSI_Data structures where values will be stored
 */
/*#############################################################################################################*/
void read_uart(HardwareSerial &uart, RSSI_Data *rssi_data);

/*#############################################################################################################*/
/**
 * @brief Check and update RSSI values based on last receive time
 * @param rssi_data Pointer to array of RSSI_Data structures to check
 *
 * If no data received for RSSI_Timeout milliseconds, set RSSI to -100 (NOT FOUND)
 */
/*#############################################################################################################*/
void check_last_receive_time(RSSI_Data *rssi_data);

#endif