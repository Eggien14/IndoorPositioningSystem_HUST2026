#ifndef DATA_HANDLE_H
#define DATA_HANDLE_H

#include "config.h"
#include "ili9341_obj.h"
#include "peripheral_handle.h"

extern String device_payload_buffer;

void handle_mqtt_topic_user_pos(UserDisplay &user_instance, const char* payload);

void handle_mqtt_topic_flames_data(FlamesDisplay &flames_instance, const char* payload);

void handle_mqtt_topic_map_data(MapDisplay &map_instance, const char* payload);

void nozzel_device_packing_mqtt_payload(IMU_Data &imu_data, Valve_Data &valve_data, String &device_payload_buffer);

void extinguisher_device_packing_mqtt_payload(IMU_Data &imu_data, Valve_Data &valve_data, String &device_payload_buffer);
#endif