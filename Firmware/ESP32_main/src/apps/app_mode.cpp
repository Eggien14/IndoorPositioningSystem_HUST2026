#include "apps/app_mode.h"

int last_data_sent[8] = {-100, -100, -100, -100, -100, -100, -100, -100};

String training_topic = MQTT_TRAINING_TOPIC; //+ String(DEVICE_ID);
String real_topic = MQTT_REALITY_TOPIC;      //+ String(DEVICE_ID);
String device_infor_topic = MQTT_DEVICE_INFOR_TOPIC;
int device_id = DEVICE_ID;

// Get mode of system based on button states
void get_mode(ModeSystem &mode_of_system)
{
    if (is_sw2_on())
    {
        mode_of_system = is_sw1_on() ? TRAINING_MODE : DEFAULT_MODE;
    }
    else
    {
        mode_of_system = is_sw1_on() ? REALITY_MODE : DEFAULT_MODE;
    }
}

bool change_mode = false;
void mode_update(ModeSystem &mode_of_system)
{
    ModeSystem new_mode;
    get_mode(new_mode);
    if (new_mode != mode_of_system)
    {
        mode_of_system = new_mode;
        change_mode = true;
    }
}

void run_default_mode(Adafruit_ILI9341 &tft, RSSI_Data *wifi_rssi_data,
                      RSSI_Data *ble_rssi_data, String &message)
{
    if (change_mode)
    {
        change_mode = false;
        lcd_default_mode_outline(tft, wifi_rssi_data, ble_rssi_data);
    }

    get_infor_msg(training_topic, real_topic, device_id, message);

    if (is_ready_to_publish())
    {
        publish_message(device_infor_topic, message);
    }
}

unsigned long last_display_time = 0;
void run_training_mode(Adafruit_ILI9341 &tft, RSSI_Data *wifi_rssi_data,
                       RSSI_Data *ble_rssi_data, IMU_Data &imu_data, String &message)
{
    if (change_mode)
    {
        change_mode = false;
        lcd_training_mode_outline(tft);
    }
    get_training_msg(wifi_rssi_data, ble_rssi_data, imu_data, message);

    if (is_ready_to_publish())
    {
        publish_message(training_topic, message);
    }
    if (millis() - last_display_time >= 100) // Update display every 1 second
    {
        last_display_time = millis();
        lcd_display_training_mode(tft, wifi_rssi_data, ble_rssi_data, imu_data);
    }
}
void run_reality_mode(Adafruit_ILI9341 &tft, RSSI_Data *wifi_rssi_data,
                      RSSI_Data *ble_rssi_data, IMU_Data &imu_data, String &message)
{
    Valve_Data valve_data;
    read_valve(&valve_data);

    if (change_mode)
    {
        change_mode = false;
        lcd_reality_mode_outline(tft);
    }
    get_real_msg(wifi_rssi_data, ble_rssi_data, imu_data, valve_data, message);

    if (is_ready_to_publish())
    {
        publish_message(real_topic, message);
    }
    lcd_display_reality_mode(tft, imu_data, map_data, user_data, fire_data, valve_data);
}
