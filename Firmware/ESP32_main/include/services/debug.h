#ifndef DEBUG_H
#define DEBUG_H

#include "config.h"

void debug_print(RSSI_Data *wifi_rssi_data, RSSI_Data *ble_rssi_data,
     IMU_Data *imu_data, String *message, ModeSystem *mode_of_system);

#endif // DEBUG_H