#ifndef BLE_HANDLE_H
#define BLE_HANDLE_H

#include "config.h"

extern esp_ble_scan_params_t ble_scan_params;

void ble_rssi_scan_callback(esp_gap_ble_cb_event_t event, esp_ble_gap_cb_param_t *param);
void uart_init(void);
void ble_init(void);

#endif