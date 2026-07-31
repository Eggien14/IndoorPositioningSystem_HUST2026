#include "services/create_msg.h"

void get_training_msg(RSSI_Data *wifi_rssi_data, RSSI_Data *ble_rssi_data,
                      IMU_Data &imu_data, String &message)
{
    JsonDocument doc;
    JsonObject rssi_wifi = doc["rssi_wifi"].to<JsonObject>();
    JsonObject rssi_ble = doc["rssi_ble"].to<JsonObject>();
    JsonObject bno = doc["bno"].to<JsonObject>();
    JsonObject acc = bno["acc"].to<JsonObject>();
    JsonObject gyro = bno["gyro"].to<JsonObject>();
    JsonObject mag = bno["mag"].to<JsonObject>();
    JsonObject euler = bno["euler"].to<JsonObject>();

    rssi_wifi["1"] = wifi_rssi_data[0].rssi;
    rssi_wifi["2"] = wifi_rssi_data[1].rssi;
    rssi_wifi["3"] = wifi_rssi_data[2].rssi;
    rssi_wifi["4"] = wifi_rssi_data[3].rssi;
    rssi_ble["1"] = ble_rssi_data[0].rssi;
    rssi_ble["2"] = ble_rssi_data[1].rssi;
    rssi_ble["3"] = ble_rssi_data[2].rssi;
    rssi_ble["4"] = ble_rssi_data[3].rssi;
    acc["x"] = imu_data.acc.x;
    acc["y"] = imu_data.acc.y;
    acc["z"] = imu_data.acc.z;
    gyro["x"] = imu_data.gyro.x;
    gyro["y"] = imu_data.gyro.y;
    gyro["z"] = imu_data.gyro.z;
    mag["x"] = imu_data.mag.x;
    mag["y"] = imu_data.mag.y;
    mag["z"] = imu_data.mag.z;
    euler["roll"] = imu_data.euler.x;
    euler["pitch"] = imu_data.euler.y;
    euler["yaw"] = imu_data.euler.z;

    serializeJson(doc, message);
}

void get_real_msg(RSSI_Data *wifi_rssi_data, RSSI_Data *ble_rssi_data,
                  IMU_Data &imu_data, Valve_Data &valve_data,
                  String &message)
{
    JsonDocument doc;
    JsonObject rssi_wifi = doc["rssi_wifi"].to<JsonObject>();
    JsonObject rssi_ble = doc["rssi_ble"].to<JsonObject>();
    JsonObject bno = doc["bno"].to<JsonObject>();
    JsonObject acc = bno["acc"].to<JsonObject>();
    JsonObject gyro = bno["gyro"].to<JsonObject>();
    JsonObject mag = bno["mag"].to<JsonObject>();
    JsonObject euler = bno["euler"].to<JsonObject>();
    JsonObject valve = doc["valve"].to<JsonObject>();

    rssi_wifi["1"] = wifi_rssi_data[0].rssi;
    rssi_wifi["2"] = wifi_rssi_data[1].rssi;
    rssi_wifi["3"] = wifi_rssi_data[2].rssi;
    rssi_wifi["4"] = wifi_rssi_data[3].rssi;
    rssi_ble["1"] = ble_rssi_data[0].rssi;
    rssi_ble["2"] = ble_rssi_data[1].rssi;
    rssi_ble["3"] = ble_rssi_data[2].rssi;
    rssi_ble["4"] = ble_rssi_data[3].rssi;
    acc["x"] = imu_data.acc.x;
    acc["y"] = imu_data.acc.y;
    acc["z"] = imu_data.acc.z;
    gyro["x"] = imu_data.gyro.x;
    gyro["y"] = imu_data.gyro.y;
    gyro["z"] = imu_data.gyro.z;
    mag["x"] = imu_data.mag.x;
    mag["y"] = imu_data.mag.y;
    mag["z"] = imu_data.mag.z;
    euler["roll"] = imu_data.euler.x;
    euler["pitch"] = imu_data.euler.y;
    euler["yaw"] = imu_data.euler.z;
    valve["open"] = valve_data.valve_open_status;
    valve["mode"] = valve_data.mode_status;

    serializeJson(doc, message);
}

void get_infor_msg(String &training_topic, String &real_topic, int &device_id, String &message)
{
    JsonDocument doc;
    doc["device_id"] = device_id;
    doc["training_topic"] = training_topic;
    doc["real_topic"] = real_topic;
    serializeJson(doc, message);
}
