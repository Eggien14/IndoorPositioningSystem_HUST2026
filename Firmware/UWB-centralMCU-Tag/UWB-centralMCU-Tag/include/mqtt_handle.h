#ifndef MQTT_HANDLE_H
#define MQTT_HANDLE_H

#include "config.h"
#include "ili9341_obj.h"
#include "data_handle.h"

extern WiFiClient wifi_client;
extern PubSubClient mqtt_client;


bool connect_wifi();

bool connect_mqtt();

void init_connection_with_mqtt_broker();

void reconnect_mqtt();

bool publish_message(String topic, String message);

void mqtt_callback(char* topic, byte* payload, unsigned int length);

void publish_mqtt_payload_device_data(String device_payload_buffer);
#endif