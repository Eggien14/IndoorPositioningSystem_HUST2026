#include <Arduino.h>
#include <BLEDevice.h>
#include <BLEAdvertising.h>
#include "esp_bt.h"

BLEAdvertising *pAdvertising;

void setup()
{
  Serial.begin(115200);

  // Set max power to +9dbm
  esp_ble_tx_power_set(ESP_BLE_PWR_TYPE_ADV, ESP_PWR_LVL_P9);

  // Initialize BLE
  BLEDevice::init("ESP32_RSSI_BEACON_1");

  // Create advertising
  pAdvertising = BLEDevice::getAdvertising();

  BLEAdvertisementData advData;
  advData.setName("BEACON_1"); // Name for identification

  // Can add custom data or leave empty
  advData.setManufacturerData("ID_01");

  pAdvertising->setAdvertisementData(advData);

  // Increase transmission speed (important for beacons)
  pAdvertising->setMinInterval(0x20);
  pAdvertising->setMaxInterval(0x20);

  pAdvertising->start();

  Serial.println("Starting BLE advertising...");
}

void loop()
{
}