#ifndef WIFI_MQTT_HANDLE_H
#define WIFI_MQTT_HANDLE_H

#include "config.h"
#include "services/mqtt_data_handle.h"



void init_wifi_mqtt(void);
void mqtt_loop(void);
bool publish_message(String topic, String message);
bool is_ready_to_publish(void);
bool is_ready_to_publish_training_mode(RSSI_Data *wifi_rssi_data,
     RSSI_Data *ble_rssi_data, int *last_data_sent);
     
void mqtt_callback(char* topic, byte* payload, unsigned int length);
#endif // WIFI_MQTT_HANDLE_H