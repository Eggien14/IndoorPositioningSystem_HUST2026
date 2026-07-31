#ifndef LCD_CONTROL_H
#define LCD_CONTROL_H

#include "config.h"
#include "services/mqtt_data_handle.h"

void lcd_display_training_mode(Adafruit_ILI9341 &tft,
     RSSI_Data *wifi_rssi_data, RSSI_Data *ble_rssi_data, IMU_Data &imu_data);
void lcd_display_reality_mode(Adafruit_ILI9341 &tft, IMU_Data &imu_data, Map_data &map_data, User_data &user_data,
     Fire_data &fire_data, Valve_Data &valve_data);
#endif // LCD_CONTROL_H