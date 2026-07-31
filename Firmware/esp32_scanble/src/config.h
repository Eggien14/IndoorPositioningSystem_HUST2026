#ifndef CONFIG_H
#define CONFIG_H

#include <stdio.h>
#include <string.h>
#include <stdlib.h>

#include "esp_wifi.h"
#include "esp_netif.h"

#include "esp_gap_ble_api.h"
#include "esp_bt.h"
#include "esp_gatts_api.h"
#include "esp_bt_main.h"

#include "esp_log.h"
#include "nvs_flash.h"
#include "esp_timer.h"

#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "freertos/semphr.h"

#include "driver/uart.h"
#include "driver/gpio.h"

#define UART_PORT UART_NUM_2
#define TXD_PIN 17
#define RXD_PIN 16

#define NUM_BEACONS 4

#endif