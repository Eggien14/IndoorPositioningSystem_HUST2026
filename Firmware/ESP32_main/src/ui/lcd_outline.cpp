#include "ui/lcd_outline.h"

void lcd_setup_intro(Adafruit_ILI9341 &tft)
{
    // Intro
    tft.fillScreen(WHITE);
    tft.setCursor(40, 50);
    tft.setTextColor(RED);
    tft.setTextSize(5);
    tft.println("iPac Lab");

    tft.setCursor(30, 150);
    tft.setTextColor(BLACK);
    tft.setTextSize(3);
    tft.println("Target Tracking");

    tft.setCursor(85, 200);
    tft.setTextColor(BLACK);
    tft.setTextSize(1);
    tft.println("Set up hardware serial...");

    delay(INTRO_TIME);

    tft.fillRect(70, 200, 170, 10, WHITE);
    tft.setCursor(70, 200);
    tft.setTextColor(BLACK);
    tft.setTextSize(1);
    tft.println("Connecting to wifi and MQTT...");
}

void lcd_setup_outline(Adafruit_ILI9341 &tft)
{
    tft.fillScreen(BLACK);
    tft.setCursor(85, 5);
    tft.setTextColor(WHITE);
    tft.setTextSize(1);
    tft.println("iPAC Lab | Target Tracking");
    tft.setCursor(5, 15);
    tft.setTextColor(WHITE);
    tft.setTextSize(1);
    tft.println("Mode:");
}

void init_lcd(Adafruit_ILI9341 &tft)
{
    tft.begin();
    tft.setRotation(LCD_ROTATION); // Set the display orientation (0-3)
    lcd_setup_intro(tft);
}

void draw_qr_code(Adafruit_ILI9341 &tft, int x, int y, int scale)
{
    for (int row = 0; row < QR_SIZE; row++)
    {
        for (int col = 0; col < QR_SIZE; col++)
        {
            uint16_t color = DEMO_QR[row][col] ? BLACK : WHITE;
            tft.fillRect(x + (col * scale), y + (row * scale), scale, scale, color);
        }
    }
}
void lcd_default_mode_outline(Adafruit_ILI9341 &tft, RSSI_Data *wifi_rssi_data, RSSI_Data *ble_rssi_data)
{
    lcd_setup_outline(tft);
    // Setup out line
    tft.setCursor(40, 15);
    tft.setTextColor(WHITE);
    tft.setTextSize(1);
    tft.println("Default");

    // Information of device
    tft.setTextColor(WHITE);

    tft.setCursor(5, 30);
    tft.setTextSize(1);
    tft.println("Device ID");
    tft.setCursor(70, 30);
    tft.println(": " + String(DEVICE_ID));

    tft.setCursor(5, 40);
    tft.println("Device Name");
    tft.setCursor(70, 40);
    tft.println(": " + String(DEVICE_NAME));

    // Information of MQTT
    tft.setTextColor(WHITE);

    tft.setCursor(5, 55);
    tft.println("Wi-Fi connected");
    tft.setCursor(100, 55);
    tft.println(": " + String(WIFI_SSID));

    tft.setCursor(5, 65);
    tft.println("Broker connected");
    tft.setCursor(100, 65);
    tft.println(": " + String(MQTT_BROKER));

    tft.setCursor(5, 75);
    tft.println("Training topic");
    tft.setCursor(100, 75);
    tft.println(": " + String(MQTT_TRAINING_TOPIC));

    tft.setCursor(5, 85);
    tft.println("Reality topic");
    tft.setCursor(100, 85);
    tft.println(": " + String(MQTT_REALITY_TOPIC));

    // Information of RSSI
    tft.setTextColor(WHITE);

    tft.setCursor(5, 100);
    tft.println("Router Wifi " + String(wifi_rssi_data[0].ssid_id));
    tft.setCursor(85, 100);
    tft.println(": " + String(wifi_rssi_data[0].ssid));

    tft.setCursor(5, 110);
    tft.println("Router Wifi " + String(wifi_rssi_data[1].ssid_id));
    tft.setCursor(85, 110);
    tft.println(": " + String(wifi_rssi_data[1].ssid));

    tft.setCursor(5, 120);
    tft.println("Router Wifi " + String(wifi_rssi_data[2].ssid_id));
    tft.setCursor(85, 120);
    tft.println(": " + String(wifi_rssi_data[2].ssid));

    tft.setCursor(5, 130);
    tft.println("Router Wifi " + String(wifi_rssi_data[3].ssid_id));
    tft.setCursor(85, 130);
    tft.println(": " + String(wifi_rssi_data[3].ssid));

    // Information of BLE RSSI
    tft.setCursor(165, 100);
    tft.println("BLE Beacon " + String(ble_rssi_data[0].ssid_id));
    tft.setCursor(240, 100);
    tft.println(": " + String(ble_rssi_data[0].ssid));

    tft.setCursor(165, 110);
    tft.println("BLE Beacon " + String(ble_rssi_data[1].ssid_id));
    tft.setCursor(240, 110);
    tft.println(": " + String(ble_rssi_data[1].ssid));

    tft.setCursor(165, 120);
    tft.println("BLE Beacon " + String(ble_rssi_data[2].ssid_id));
    tft.setCursor(240, 120);
    tft.println(": " + String(ble_rssi_data[2].ssid));

    tft.setCursor(165, 130);
    tft.println("BLE Beacon " + String(ble_rssi_data[3].ssid_id));
    tft.setCursor(240, 130);
    tft.println(": " + String(ble_rssi_data[3].ssid));

    // Turtorial
    tft.setTextColor(WHITE);

    tft.setCursor(5, 145);
    tft.println("Guide: " + String(YOUTUBE_LINK));
    draw_qr_code(tft, 5, 160, 2);

    tft.setTextColor(RED);
    tft.setCursor(80, 160);
    tft.println("SYSTEM MODE SWITCH");
    tft.setTextColor(WHITE);
    tft.setCursor(200, 160);
    tft.println(": Press to switch");
    tft.setCursor(80, 170);
    tft.println("Reality mode <-> Training mode");

    tft.setTextColor(GREEN);
    tft.setCursor(80, 185);
    tft.println("ENABLE MSG SWITCH");
    tft.setTextColor(WHITE);
    tft.setCursor(200, 185);
    tft.println(": Press to switch");
    tft.setCursor(80, 195);
    tft.println("Default mode <-> Training/Reality mode");
}

void lcd_training_mode_outline(Adafruit_ILI9341 &tft)
{
    lcd_setup_outline(tft);
    tft.setCursor(40, 15);
    tft.setTextColor(RED);
    tft.setTextSize(1);
    tft.println("TRAINING");

    tft.setTextColor(WHITE);
    tft.setCursor(5, 35);
    tft.println("WIFI RSSI data");
    tft.setCursor(15, 50);
    tft.println("Router_ID:");
    tft.setCursor(85, 50);
    tft.println(" | RSSI:");
    tft.setCursor(15, 60);
    tft.println("Router_ID:");
    tft.setCursor(85, 60);
    tft.println(" | RSSI:");
    tft.setCursor(15, 70);
    tft.println("Router_ID:");
    tft.setCursor(85, 70);
    tft.println(" | RSSI:");
    tft.setCursor(15, 80);
    tft.println("Router_ID:");
    tft.setCursor(85, 80);
    tft.println(" | RSSI:");

    tft.setTextColor(WHITE);
    tft.setCursor(5, 100);
    tft.println("BLE RSSI data");
    tft.setCursor(15, 115);
    tft.println("Beacon_ID:");
    tft.setCursor(85, 115);
    tft.println(" | RSSI:");
    tft.setCursor(15, 125);
    tft.println("Beacon_ID:");
    tft.setCursor(85, 125);
    tft.println(" | RSSI:");
    tft.setCursor(15, 135);
    tft.println("Beacon_ID:");
    tft.setCursor(85, 135);
    tft.println(" | RSSI:");
    tft.setCursor(15, 145);
    tft.println("Beacon_ID:");
    tft.setCursor(85, 145);
    tft.println(" | RSSI:");

    tft.setCursor(5, 165);
    tft.println("IMU data");
    tft.setCursor(15, 180);
    tft.println("Acc[x,y,z]");
    tft.setCursor(85, 180);
    tft.println(" | x: ");
    tft.setCursor(160, 180);
    tft.println(" | y: ");
    tft.setCursor(235, 180);
    tft.println(" | z: ");
    tft.setCursor(15, 190);
    tft.println("Mag[x,y,z]");
    tft.setCursor(85, 190);
    tft.println(" | x: ");
    tft.setCursor(160, 190);
    tft.println(" | y: ");
    tft.setCursor(235, 190);
    tft.println(" | z: ");
    tft.setCursor(15, 200);
    tft.println("Gyro[x,y,z]");
    tft.setCursor(85, 200);
    tft.println(" | x: ");
    tft.setCursor(160, 200);
    tft.println(" | y: ");
    tft.setCursor(235, 200);
    tft.println(" | z: ");
    tft.setCursor(15, 210);
    tft.println("Euler[x,y,z]");
    tft.setCursor(85, 210);
    tft.println(" | x: ");
    tft.setCursor(160, 210);
    tft.println(" | y: ");
    tft.setCursor(235, 210);
    tft.println(" | z: ");
}

void lcd_reality_mode_outline(Adafruit_ILI9341 &tft)
{
    tft.fillScreen(BLACK);
    tft.setCursor(15, 5);
    tft.setTextColor(WHITE);
    tft.setTextSize(1);
    tft.println("iPAC Lab | Target Tracking");
    tft.setCursor(250, 5);
    tft.setTextColor(RED);
    tft.setTextSize(1);
    tft.println("REALITY");

    // User score table
    tft.drawFastVLine(220, 21, 49, STATIC_TEXT_COLOR);
    tft.drawFastVLine(319, 21, 49, STATIC_TEXT_COLOR);
    tft.drawFastHLine(220, 21, 99, STATIC_TEXT_COLOR);
    tft.drawFastHLine(220, 35, 99, STATIC_TEXT_COLOR);
    tft.drawFastHLine(220, 70, 99, STATIC_TEXT_COLOR);
    tft.drawFastHLine(220, 78, 99, STATIC_TEXT_COLOR);

    tft.setTextColor(WHITE);
    tft.setTextSize(1);
    tft.setCursor(240, 24);
    tft.println("User score");
    tft.setCursor(220, 85);
    tft.println("Valve Opening:");
    tft.setCursor(220, 133);

    tft.fillCircle(230, 150, 4, BLUE);
    tft.setCursor(240, 146);
    tft.println("DEFAULT MODE");

    tft.fillCircle(230, 165, 4, YELLOW);
    tft.setCursor(240, 161);
    tft.println("TRAINING MODE");
}
