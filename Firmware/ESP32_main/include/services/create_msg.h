#ifndef CREATE_MSG_H
#define CREATE_MSG_H

#include "config.h"

void get_training_msg(RSSI_Data *wifi_rssi_data, RSSI_Data *ble_rssi_data,
                      IMU_Data &imu_data, String &message);
void get_training_msg_v2(RSSI_Data *wifi_rssi_data, RSSI_Data *ble_rssi_data,
                         IMU_Data &imu_data, String &message);
void get_real_msg(RSSI_Data *wifi_rssi_data, RSSI_Data *ble_rssi_data,
                  IMU_Data &imu_data, Valve_Data &valve_data,
                  String &message);
void get_infor_msg(String &training_topic, String &real_topic, int &device_id, String &message);

#endif // CREATE_MSG_H