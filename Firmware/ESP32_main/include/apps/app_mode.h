#ifndef APP_MODE_H
#define APP_MODE_H

#include "config.h"
#include "services/button_handle.h"
#include "services/create_msg.h"
#include "services/wifi_mqtt_handle.h"
#include "services/read_valve.h"
#include "ui/lcd_outline.h"
#include "ui/lcd_control.h"

void get_mode(ModeSystem &mode_of_system);
void mode_update(ModeSystem &mode_of_system);
void run_default_mode(Adafruit_ILI9341 &tft, RSSI_Data *wifi_rssi_data,
                      RSSI_Data *ble_rssi_data, String &message);
void run_training_mode(Adafruit_ILI9341 &tft, RSSI_Data *wifi_rssi_data,
                       RSSI_Data *ble_rssi_data, IMU_Data &imu_data, String &message);
void run_reality_mode(Adafruit_ILI9341 &tft, RSSI_Data *wifi_rssi_data,
                      RSSI_Data *ble_rssi_data, IMU_Data &imu_data, String &message);

#endif // APP_MODE_H