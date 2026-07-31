#include "services/debug.h"

unsigned long last_debug_time = 0;

void print_RSSI_data(RSSI_Data *wifi_rssi_data, RSSI_Data *ble_rssi_data)
{
    Serial.printf("WIFI: %d;%d;%d;%d  BLE: %d;%d;%d;%d\n",
                  wifi_rssi_data[0].rssi, wifi_rssi_data[1].rssi,
                  wifi_rssi_data[2].rssi, wifi_rssi_data[3].rssi,
                  ble_rssi_data[0].rssi, ble_rssi_data[1].rssi,
                  ble_rssi_data[2].rssi, ble_rssi_data[3].rssi);
}

void print_IMU_data(IMU_Data *imu_data)
{
    Serial.print("| Acc: ");
    Serial.print(imu_data->acc.x);
    Serial.print(" ");
    Serial.print(imu_data->acc.y);
    Serial.print(" ");
    Serial.print(imu_data->acc.z);
    Serial.print("\n| Mag: ");
    Serial.print(imu_data->mag.x);
    Serial.print(" ");
    Serial.print(imu_data->mag.y);
    Serial.print(" ");
    Serial.print(imu_data->mag.z);
    Serial.print("\n| Gyro: ");
    Serial.print(imu_data->gyro.x);
    Serial.print(" ");
    Serial.print(imu_data->gyro.y);
    Serial.print(" ");
    Serial.print(imu_data->gyro.z);
    Serial.print("\n| Euler: ");
    Serial.print(imu_data->euler.x);
    Serial.print(" ");
    Serial.print(imu_data->euler.y);
    Serial.print(" ");
    Serial.println(imu_data->euler.z);
}

void print_topic_and_message(String *message, ModeSystem *mode_of_system)
{
    if (*mode_of_system == DEFAULT_MODE)
    {
        Serial.print("| MODE ");
        Serial.print(*mode_of_system);
        Serial.print(": DEFAULT ");
        Serial.print("| Topic: ");
        Serial.print(MQTT_DEVICE_INFOR_TOPIC);
    }
    else if (*mode_of_system == TRAINING_MODE)
    {
        Serial.print("| MODE ");
        Serial.print(*mode_of_system);
        Serial.print(": TRAINING ");
        Serial.print("| Topic: ");
        Serial.print(MQTT_TRAINING_TOPIC);
    }
    else if (*mode_of_system == REALITY_MODE)
    {
        Serial.print("| MODE ");
        Serial.print(*mode_of_system);
        Serial.print(": REALITY ");
        Serial.print("| Topic: ");
        Serial.print(MQTT_REALITY_TOPIC);
    }
    Serial.print(" | Message: ");
    Serial.println(*message);
}

void debug_print(RSSI_Data *wifi_rssi_data, RSSI_Data *ble_rssi_data, IMU_Data *imu_data, String *message, ModeSystem *mode_of_system)
{
    unsigned long currentMillis = millis();
    if (currentMillis - last_debug_time >= DEBUG_INTERVAL)
    {
        last_debug_time = currentMillis;
        // Serial.println(*message);
        //  print_RSSI_data(wifi_rssi_data, ble_rssi_data);
        print_IMU_data(imu_data);
        // print_topic_and_message(message, mode_of_system);
    }
}