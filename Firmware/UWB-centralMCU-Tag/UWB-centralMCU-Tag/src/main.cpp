#include "config.h"
#include "data_handle.h"
#include "ili9341_obj.h"
#include "ili9341_ui.h"
#include "mqtt_handle.h"
#include "peripheral_handle.h"



void setup() {

    // --- Set up Serial Monitor ---
    Serial.begin(BAUD_RATE_SERIAL);

    // --- Initialize GPIO pins for buttons and analog inputs ---
    init_button_and_valve();

    // --- Initialize internal BNO055 --- 
    init_on_device_bno055();

    // --- Initialize extenal BNO055 --- 
    init_ext_device_bno055();

    // --- Initialize internal/extenal BNO055 ---
    #if (DEVICE_TYPE == TYPE_NOZZLE)
        init_on_device_bno055();
    #elif (DEVICE_TYPE == TYPE_EXTINGUISHER)
        // init_on_device_bno055();
        init_ext_device_bno055();
    #endif

    // --- Initialize TFT display ---
    TFT_setup(tft);
    tft_setup_intro(tft);
    tft_setup_static_ui(tft);

    // --- Set up WiFi and MQTT connection ---
    init_connection_with_mqtt_broker();

}

void loop() {

    if (!mqtt_client.connected()) {
        reconnect_mqtt();
    }
    mqtt_client.loop();


    #if (DEVICE_TYPE == TYPE_NOZZLE)

        // Internal BNO055
        read_IMU_data(&int_imu_data, INT_BNO055_ADDRESS);

        // Valve data (Valve open status & valve mode)
        read_valve_open_status(valve_data);

        // MQTT Handle
        nozzel_device_packing_mqtt_payload(int_imu_data, valve_data, device_payload_buffer);
        publish_mqtt_payload_device_data(device_payload_buffer);

        // TFT Handle
        tft_main_loop_handler(tft, user, flames, exercise_map, int_imu_data, valve_data);

    #elif (DEVICE_TYPE == TYPE_EXTINGUISHER)
        // External BNO055
        read_IMU_data(&ext_imu_data, EXT_BNO055_ADDRESS);

        // Valve data (Valve open status)
        read_valve_open_status(valve_data);

        // MQTT Handle
        extinguisher_device_packing_mqtt_payload(ext_imu_data, valve_data, device_payload_buffer)
        publish_mqtt_payload_device_data(device_payload_buffer);

        // TFT Handle
        tft_main_loop_handler(tft, user, flames, exercise_map, ext_imu_data, valve_data);
    #endif

}

