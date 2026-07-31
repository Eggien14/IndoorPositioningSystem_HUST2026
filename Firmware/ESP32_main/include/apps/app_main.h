#ifndef APP_MAIN_H
#define APP_MAIN_H

#include "config.h"

#include "services/read_esp32.h"
#include "services/read_imu.h"
#include "services/read_valve.h"
#include "services/button_handle.h"
#include "services/wifi_mqtt_handle.h"
#include "services/debug.h"

#include "apps/app_mode.h"

#include "ui/lcd_outline.h"

void app_setup();
void app_loop();

#endif // APP_MAIN_H