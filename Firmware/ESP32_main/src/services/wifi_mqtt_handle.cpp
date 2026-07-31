#include "services/wifi_mqtt_handle.h"


WiFiClient wifi_client;
PubSubClient mqtt_client(wifi_client);

String map_data_topic = "map_data/" + String(DEVICE_ID);
String user_data_topic = "user_pos/" + String(DEVICE_ID);
String fire_data_topic = "fire_data/" + String(DEVICE_ID);

bool connect_wifi() {
    WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
    unsigned long start_time = millis();
    
    while (WiFi.status() != WL_CONNECTED) {
        if (millis() - start_time > WIFI_TIMEOUT) {
            return false;
        }
        delay(100);
    }
    return true;
}

bool connect_mqtt() {
    mqtt_client.setServer(MQTT_BROKER, MQTT_PORT);       
    if (!mqtt_client.connected()) {
        return mqtt_client.connect(MQTT_CLIENT_ID);
    }
    return true;
}

void mqtt_callback(char* topic, byte* payload, unsigned int length) {
    // Normalize message
    char message[length + 1];
    memcpy(message, payload, length);
    message[length] = '\0';

    // Redirect callback handle based on topic
    if (strcmp(topic, user_data_topic.c_str()) == 0) {
        handle_user_data_topic(message);
    }
    else if(strcmp(topic, fire_data_topic.c_str()) == 0){
       handle_fire_data_topic(message);
    }
    else if(strcmp(topic, map_data_topic.c_str()) == 0){
        handle_map_data_topic(message);
    }
}

void init_wifi_mqtt() {
    if (!connect_wifi())
    {
        Serial.println("WiFi connection failed!");
        return;
    }

    if (!connect_mqtt())
    {
        Serial.println("MQTT connection failed!");
        return;
    }
    Serial.printf("CONNECTED WIFI.\n");
    mqtt_client.subscribe(map_data_topic.c_str());
    mqtt_client.subscribe(user_data_topic.c_str());
    mqtt_client.subscribe(fire_data_topic.c_str());
    mqtt_client.setCallback(mqtt_callback);
}

void mqtt_loop() {
    mqtt_client.loop();
}

bool publish_message(String topic, String message) {
    if (!mqtt_client.connected()) {
        if (!connect_mqtt()) {
            Serial.println("MQTT connection failed!");
            return false;
        }
    }
    return mqtt_client.publish(topic.c_str(), message.c_str());
}

unsigned long last_publish_time = 0;
bool is_ready_to_publish() {
    unsigned long current_time = millis();
    if (current_time - last_publish_time >= PUBLISH_INTERVAL) 
    {
        last_publish_time = current_time;
        return true;
    }
    return false;
}

bool is_ready_to_publish_training_mode(RSSI_Data *wifi_rssi_data,
     RSSI_Data *ble_rssi_data, int *last_data_sent) {
    unsigned long current_time = millis();
    if (current_time - last_publish_time >= PUBLISH_INTERVAL) 
    {
        int data_changed = 0;
        // Check if there is any change in the RSSI data compared to the last sent data
        for (int i = 0; i < 4; i++) {
            if (wifi_rssi_data[i].rssi != last_data_sent[i]) {
                last_data_sent[i] = wifi_rssi_data[i].rssi;
                data_changed++;
            }
            if (ble_rssi_data[i].rssi != last_data_sent[i + 4]) {
                last_data_sent[i + 4] = ble_rssi_data[i].rssi;
                data_changed++;
            }
        }
        last_publish_time = current_time;
        Serial.printf("%d\n",data_changed);
        if (data_changed > 2) {
            return true;
        }
    }
    return false;
}