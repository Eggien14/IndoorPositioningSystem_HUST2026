#ifndef MQTT_DATA_HANDLE_H
#define MQTT_DATA_HANDLE_H

#include <config.h>

extern float north_offset;
extern Map_data map_data;   
extern Fire_data fire_data;
extern User_data user_data;

extern bool map_updated;
extern bool fire_updated;
extern bool user_updated;

void handle_map_data_topic(const char* payload);
void handle_user_data_topic(const char* payload);
void handle_fire_data_topic(const char* payload);

#endif // MQTT_DATA_HANDLE_H