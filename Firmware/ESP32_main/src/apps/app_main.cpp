#include "apps/app_main.h"

// Set up Hardware Serial for UART communication
HardwareSerial uart_esp_wifi(UART_ID_ESP_WIFI);
HardwareSerial uart_esp_ble(UART_ID_ESP_BLE);
// Variables for saving RSSI data
RSSI_Data wifi_rssi_data[4] = {
    {"RSSI1", 1, -100, 0},
    {"RSSI2", 2, -100, 0},
    {"RSSI3", 3, -100, 0},
    {"RSSI4", 4, -100, 0}};

RSSI_Data ble_rssi_data[4] = {
    {"Beacon1", 1, -100, 0},
    {"Beacon2", 2, -100, 0},
    {"Beacon3", 3, -100, 0},
    {"Beacon4", 4, -100, 0}};

// Variables for IMU data
IMU_Data imu_ex_data;
IMU_Data imu_in_data;

// Variable for system mode
ModeSystem mode_of_system = DEFAULT_MODE;

// Initialize Adafruit ILI9341 TFT display
Adafruit_ILI9341 tft = Adafruit_ILI9341(TFT_CS, TFT_DC, TFT_RST);

// Messeage to be published to MQTT
String message = "";
unsigned long last_sent;

void app_setup()
{
    Serial.begin(BAUD_RATE_SERIAL);
    init_uart_esp32(uart_esp_wifi, uart_esp_ble);
    init_IMU();
    init_button();
    init_valve();
    init_lcd(tft);
    init_wifi_mqtt();
    lcd_setup_outline(tft);
    Serial.printf("Set up finished.\n");
}
void app_loop()
{
    // Handle MQTT loop
    mqtt_loop();
    // Read UART data from ESP32
    read_esp32(uart_esp_wifi, uart_esp_ble, wifi_rssi_data, ble_rssi_data);
    // Read IMU data from BNO055
    // read_IMU_data(&imu_ex_data, BNO055_EX_ADDRESS);
    read_IMU_data(&imu_in_data, BNO055_IN_ADDRESS);

    // Check if mode has changed
    mode_update(mode_of_system);

    // run the corresponding mode function based on the current mode of system
    switch (mode_of_system)
    {
    case DEFAULT_MODE:
        run_default_mode(tft, wifi_rssi_data, ble_rssi_data, message);
        break;
    case TRAINING_MODE:
        run_training_mode(tft, wifi_rssi_data, ble_rssi_data, imu_in_data, message);
        break;
    case REALITY_MODE:
        run_reality_mode(tft, wifi_rssi_data, ble_rssi_data, imu_in_data, message);
        break;
    }
}
