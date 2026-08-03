#ifndef ILI9341_UI_H
#define ILI9341_UI_H

#include "config.h"
#include "ili9341_obj.h"

void tft_setup_intro(Adafruit_ILI9341 &tft);

void tft_setup_static_ui(Adafruit_ILI9341 &tft);

void tft_main_loop_handler(Adafruit_ILI9341 &tft, UserDisplay &user, FlamesDisplay &flames, 
                            MapDisplay &map, IMU_Data &imu_data, Valve_Data &valve_data);

#endif