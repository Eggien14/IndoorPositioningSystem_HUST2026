#include "data_handle.h"

String device_payload_buffer = "";

/*--------------------------------------------------------------------------------------------------------*/
/**
 * @brief Handle User data topic
 */
/*--------------------------------------------------------------------------------------------------------*/
void handle_mqtt_topic_user_pos(UserDisplay &user_instance, const char* payload)
{
    //De-serialise payload
    JsonDocument doc;
    DeserializationError error = deserializeJson(doc, payload);

    // Error debug
    if (error) {
        Serial.print("[user_pos]: Invalid JSON format\r\n");
        // Serial.println(error.c_str());
        return; 
    }

    // Extract key-value
    float x = doc["x"];
    float y = doc["y"];
    int score = doc["score"];

    // user_instance.hasNewData();
    user_instance.updateData(x, y, score);
}


/*--------------------------------------------------------------------------------------------------------*/
/**
 * @brief Handle Flames data topic
 */
/*--------------------------------------------------------------------------------------------------------*/
void handle_mqtt_topic_flames_data(FlamesDisplay &flames_instance, const char* payload)
{
    // flames_instance.hasNewData();
    flames_instance.updateData(payload);
    // Serial.println("Flames updated!\r\n");
}


/*--------------------------------------------------------------------------------------------------------*/
/**
 * @brief Handle Map data topic
 */
/*--------------------------------------------------------------------------------------------------------*/
void handle_mqtt_topic_map_data(MapDisplay &map_instance, const char* payload)
{
    // map_instance.hasNewData();
    map_instance.updateData(payload);
    // Serial.println("Map updated!\r\n");
}


/*--------------------------------------------------------------------------------------------------------*/
/**
 * @brief Packing nozzel_device telementy data payload
 */
/*--------------------------------------------------------------------------------------------------------*/
void nozzel_device_packing_mqtt_payload(IMU_Data &imu_data, Valve_Data &valve_data, String &device_payload_buffer){
    JsonDocument doc;

    JsonObject bno = doc["bno"].to<JsonObject>();

    JsonObject acc = bno["acc"].to<JsonObject>();
    acc["x"] = imu_data.acc.x;
    acc["y"] = imu_data.acc.y;
    acc["z"] = imu_data.acc.z;
    
    JsonObject gyro = bno["gyro"].to<JsonObject>();
    gyro["x"] = imu_data.gyro.x;
    gyro["y"] = imu_data.gyro.y;
    gyro["z"] = imu_data.gyro.z;
    
    JsonObject mag = bno["mag"].to<JsonObject>();
    mag["x"] = imu_data.mag.x;
    mag["y"] = imu_data.mag.y;
    mag["z"] = imu_data.mag.z;
    
    JsonObject euler = bno["euler"].to<JsonObject>();
    euler["yaw"]   = imu_data.euler.z; 
    euler["roll"]  = imu_data.euler.x;
    euler["pitch"] = imu_data.euler.y;

    JsonObject valve = doc["valve"].to<JsonObject>();
    valve["open"] = (float)valve_data.valve_open_status;
    valve["mode"] = (float)valve_data.mode_status;

    // Defaut "0", handle later
    JsonObject button = doc["button"].to<JsonObject>();
    button["A"] = 0;
    button["B"] = 0;
    button["C"] = 0;

    device_payload_buffer = ""; 
    serializeJson(doc, device_payload_buffer);
}


/*--------------------------------------------------------------------------------------------------------*/
/**
 * @brief Packing extinguisher_device telementy data payload (Support in the future)
 */
/*--------------------------------------------------------------------------------------------------------*/
void extinguisher_device_packing_mqtt_payload(IMU_Data &imu_data, Valve_Data &valve_data, String &device_payload_buffer){

}
