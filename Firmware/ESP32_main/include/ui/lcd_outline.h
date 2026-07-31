#ifndef LCD_OUTLINE_H
#define LCD_OUTLINE_H

#include "config.h"

void init_lcd(Adafruit_ILI9341 &tft);
void lcd_setup_outline(Adafruit_ILI9341 &tft);
void lcd_default_mode_outline(Adafruit_ILI9341 &tft, RSSI_Data *wifi_rssi_data,
     RSSI_Data *ble_rssi_data);
void lcd_training_mode_outline(Adafruit_ILI9341 &tft);
void lcd_reality_mode_outline(Adafruit_ILI9341 &tft);

#endif // LCD_OUTLINE_H