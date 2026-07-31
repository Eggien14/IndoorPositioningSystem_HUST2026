#include "ui/lcd_control.h"

extern Map_data map_data;
extern float north_offset;
extern int fire_map[MAP_WIDTH_MAX][MAP_HEIGHT_MAX];
extern User_data user_data;

unsigned char fire_bitmap[] PROGMEM =
    {
        0xff, 0xff, 0xfe, 0xff, 0xfc, 0xff, 0xfc, 0xff, 0xfc, 0x5f, 0xfc, 0x0f, 0xec, 0x0f, 0xce, 0x0f,
        0xc4, 0x13, 0xc0, 0x03, 0xc0, 0x03, 0xe0, 0x03, 0xe0, 0x07, 0xf0, 0x0f, 0xf8, 0x1f, 0xfe, 0x7f};

void evaluate_rssi_value(Adafruit_ILI9341 &tft, int rssi_value, int x, int y)
{
    if (rssi_value == -100)
    {
        tft.setCursor(x, y);
        tft.setTextColor(RED);
        tft.println("Lost signal");
        tft.setTextColor(WHITE);
    }
    else if (rssi_value > -100 && rssi_value < -80)
    {
        tft.setCursor(x, y);
        tft.setTextColor(ORANGE);
        tft.println("Weak");
        tft.setTextColor(WHITE);
    }
    else if (rssi_value >= -80 && rssi_value <= -30)
    {
        tft.setCursor(x, y);
        tft.setTextColor(YELLOW);
        tft.println("Normal");
        tft.setTextColor(WHITE);
    }
    else if (rssi_value > -30 && rssi_value < 0)
    {
        tft.setCursor(x, y);
        tft.setTextColor(GREEN);
        tft.println("Strong");
        tft.setTextColor(WHITE);
    }
    else
    {
        tft.setCursor(x, y);
        tft.setTextColor(RED);
        tft.println("Not Valid");
        tft.setTextColor(WHITE);
    }
}
void lcd_display_training_mode(Adafruit_ILI9341 &tft,
                               RSSI_Data *wifi_rssi_data, RSSI_Data *ble_rssi_data, IMU_Data &imu_data)
{
    // RSSI data
    // Clear previous data
    tft.fillRect(70, 50, 14, 40, BLACK);
    tft.fillRect(140, 50, 200, 40, BLACK);

    tft.setTextColor(WHITE);
    tft.setCursor(70, 50);
    tft.println(String(wifi_rssi_data[0].ssid_id));
    tft.setCursor(140, 50);
    tft.println(String(wifi_rssi_data[0].rssi));
    evaluate_rssi_value(tft, wifi_rssi_data[0].rssi, 200, 50);

    tft.setCursor(70, 60);
    tft.println(String(wifi_rssi_data[1].ssid_id));
    tft.setCursor(140, 60);
    tft.println(String(wifi_rssi_data[1].rssi));
    evaluate_rssi_value(tft, wifi_rssi_data[1].rssi, 200, 60);

    tft.setCursor(70, 70);
    tft.println(String(wifi_rssi_data[2].ssid_id));
    tft.setCursor(140, 70);
    tft.println(String(wifi_rssi_data[2].rssi));
    evaluate_rssi_value(tft, wifi_rssi_data[2].rssi, 200, 70);

    tft.setCursor(70, 80);
    tft.println(String(wifi_rssi_data[3].ssid_id));
    tft.setCursor(140, 80);
    tft.println(String(wifi_rssi_data[3].rssi));
    evaluate_rssi_value(tft, wifi_rssi_data[3].rssi, 200, 80);

    // BLE RSSI data
    tft.fillRect(70, 115, 14, 40, BLACK);
    tft.fillRect(140, 115, 200, 40, BLACK);

    tft.setTextColor(WHITE);
    tft.setCursor(70, 115);
    tft.println(String(ble_rssi_data[0].ssid_id));
    tft.setCursor(140, 115);
    tft.println(String(ble_rssi_data[0].rssi));
    evaluate_rssi_value(tft, ble_rssi_data[0].rssi, 200, 115);

    tft.setCursor(70, 125);
    tft.println(String(ble_rssi_data[1].ssid_id));
    tft.setCursor(140, 125);
    tft.println(String(ble_rssi_data[1].rssi));
    evaluate_rssi_value(tft, ble_rssi_data[1].rssi, 200, 125);

    tft.setCursor(70, 135);
    tft.println(String(ble_rssi_data[2].ssid_id));
    tft.setCursor(140, 135);
    tft.println(String(ble_rssi_data[2].rssi));
    evaluate_rssi_value(tft, ble_rssi_data[2].rssi, 200, 135);

    tft.setCursor(70, 145);
    tft.println(String(ble_rssi_data[3].ssid_id));
    tft.setCursor(140, 145);
    tft.println(String(ble_rssi_data[3].rssi));
    evaluate_rssi_value(tft, ble_rssi_data[3].rssi, 200, 145);

    // IMU data
    // Clear previous data
    tft.fillRect(120, 180, 39, 40, BLACK);
    tft.fillRect(195, 180, 39, 40, BLACK);
    tft.fillRect(270, 180, 39, 40, BLACK);

    tft.setCursor(120, 180);
    tft.println(String(imu_data.acc.x));
    tft.setCursor(195, 180);
    tft.println(String(imu_data.acc.y));
    tft.setCursor(270, 180);
    tft.println(String(imu_data.acc.z));

    tft.setCursor(120, 190);
    tft.println(String(imu_data.mag.x));
    tft.setCursor(195, 190);
    tft.println(String(imu_data.mag.y));
    tft.setCursor(270, 190);
    tft.println(String(imu_data.mag.z));

    tft.setCursor(120, 200);
    tft.println(String(imu_data.gyro.x));
    tft.setCursor(195, 200);
    tft.println(String(imu_data.gyro.y));
    tft.setCursor(270, 200);
    tft.println(String(imu_data.gyro.z));

    tft.setCursor(120, 210);
    tft.println(String(imu_data.euler.x));
    tft.setCursor(195, 210);
    tft.println(String(imu_data.euler.y));
    tft.setCursor(270, 210);
    tft.println(String(imu_data.euler.z));
}

////////////////////////////////////////////////////////////////////////////////////////////////////////////
void coordinate_to_pixel(float coor_x, float coor_y, int &pixel_x, int &pixel_y)
{
    // Normalize outlier
    if (coor_x < 0)
        coor_x = 0;
    if (coor_x > 10)
        coor_x = 10;
    if (coor_y < 0)
        coor_y = 0;
    if (coor_y > 10)
        coor_y = 10;

    // X: Mapping from 0–10 (descartes) to 9–211 (pixel)
    pixel_x = round(9 + (coor_x / 10.00f) * (211 - 9));
    // Y: Mapping from 0–10 (descartes) to 221–19 (pixel) (reverse y axis with ILI9341)
    pixel_y = round(221 - (coor_y / 10.00f) * (221 - 19));
}

void lcd_setup_map_outline(Adafruit_ILI9341 &tft)
{
    tft.setTextColor(STATIC_TEXT_COLOR);
    tft.setTextSize(1);

    // Vẽ các trục của map
    tft.drawFastVLine(9, 19, 202, MAP_GRID_COLOR);
    tft.drawFastHLine(9, 221, 202, MAP_GRID_COLOR);
    tft.drawFastVLine(217, 0, 240, MAP_GRID_COLOR);

    // Trục Y - Hướng north của map
    tft.setCursor(0, 16);
    tft.println("10");
    tft.setCursor(1, 36);
    tft.println("9");
    tft.setCursor(1, 56);
    tft.println("8");
    tft.setCursor(1, 76);
    tft.println("7");
    tft.setCursor(1, 96);
    tft.println("6");
    tft.setCursor(1, 116);
    tft.println("5");
    tft.setCursor(1, 136);
    tft.println("4");
    tft.setCursor(1, 156);
    tft.println("3");
    tft.setCursor(1, 176);
    tft.println("2");
    tft.setCursor(1, 196);
    tft.println("1");

    // Trục x
    tft.setCursor(27, 226);
    tft.println("1");
    tft.setCursor(47, 226);
    tft.println("2");
    tft.setCursor(67, 226);
    tft.println("3");
    tft.setCursor(87, 226);
    tft.println("4");
    tft.setCursor(107, 226);
    tft.println("5");
    tft.setCursor(127, 226);
    tft.println("6");
    tft.setCursor(147, 226);
    tft.println("7");
    tft.setCursor(167, 226);
    tft.println("8");
    tft.setCursor(187, 226);
    tft.println("9");
    tft.setCursor(207, 226);
    tft.println("10");
    tft.setCursor(1, 226);
    tft.println("0");
}

void lcd_clear_map(Adafruit_ILI9341 &tft)
{
    tft.fillRect(10, 21, 200, 200, BACKGROUND_COLOR);
}

void lcd_display_map(Adafruit_ILI9341 &tft, Map_data &map_data)
{
    int pixel_x, pixel_y;

    // Browse through all 10x10 grid
    for (int x = 0; x < 10; x++)
    {
        for (int y = 0; y < 10; y++)
        {

            // Lấy tọa độ góc trên bên trái của ô lưới để vẽ
            coordinate_to_pixel(x, y, pixel_x, pixel_y);

            if (map_data.map_cells[x][y] == 1)
            {
                // Draw passable grid
                tft.drawRect(pixel_x, pixel_y - 20, 21, 21, MAP_GRID_COLOR);
            }
            // else {
            //     // Draw unpassable grid
            //     tft.drawLine(pixel_x, pixel_y - 10, pixel_x + 10, pixel_y - 20, NOT_MAP_GRID_COLOR);
            //     tft.drawLine(pixel_x + 10, pixel_y, pixel_x + 20, pixel_y -10, NOT_MAP_GRID_COLOR);
            // }
        }
    }
}
void lcd_display_fire(Adafruit_ILI9341 &tft, Fire_data &fire_data)
{
    // Draw new fire
    for (int x = 0; x < MAP_WIDTH_MAX; x++)
    {
        for (int y = 0; y < MAP_HEIGHT_MAX; y++)
        {
            if (fire_data.fire_map[x][y] == 0) // Delete fire
            {
                int pixel_x, pixel_y;
                coordinate_to_pixel(x, y, pixel_x, pixel_y);
                tft.fillRect(pixel_x + 1, pixel_y - 19, 18, 18, BACKGROUND_COLOR);
            }
            else
            {

                int pixel_x, pixel_y;
                coordinate_to_pixel(x, y, pixel_x, pixel_y);
                tft.drawBitmap(pixel_x + 2, pixel_y - 18, fire_bitmap, 16, 16, fire_color[fire_data.fire_map[x][y]]);
                // tft.fillRect(pixel_x + 2, pixel_y - 18, 16, 16, fire_color[fire_data.fire_map[x][y]]);
            }
        }
    }
}

void lcd_clear_user(Adafruit_ILI9341 &tft, Map_data &map_data, IMU_Data &imu_data, Valve_Data &valve_data)
{
    int cx, cy;
    coordinate_to_pixel(user_data.last_user_x, user_data.last_user_y, cx, cy);

    if (user_data.prev_vision_range > 0)
    {
        const int num_segments = 6;
        float total_view_angle_rad = user_data.prev_view_cone_angle * (PI / 180.0f);
        float angle_step = total_view_angle_rad / num_segments;

        float start_angle = user_data.prev_yaw_angle - (total_view_angle_rad / 2.0f);

        int prev_x = cx + round(user_data.prev_vision_range * sin(start_angle));
        int prev_y = cy - round(user_data.prev_vision_range * cos(start_angle));

        for (int i = 1; i <= num_segments; i++)
        {
            float current_angle = start_angle + (i * angle_step);
            int next_x = cx + round(user_data.prev_vision_range * sin(current_angle));
            int next_y = cy - round(user_data.prev_vision_range * cos(current_angle));

            tft.fillTriangle(cx, cy, prev_x, prev_y, next_x, next_y, BACKGROUND_COLOR);

            prev_x = next_x;
            prev_y = next_y;
        }
    }

    // Delete user
    tft.fillCircle(cx, cy, 5, BACKGROUND_COLOR);
}

void lcd_display_user(Adafruit_ILI9341 &tft, Map_data &map_data, User_data &user_data, IMU_Data &imu_data, Valve_Data &valve_data)
{
    user_data.curr_yaw_angle = (imu_data.euler.z - map_data.north_offset) * (PI / 180.0f);

    int cx, cy;
    coordinate_to_pixel(user_data.user_x, user_data.user_y, cx, cy);

    // Calculate user vison_range based on valve_open_status and mode_status
    if (valve_data.mode_status < 50)
    {
        // Jet Mode
        user_data.curr_view_cone_angle = 20.0f;
        // 2.5 grid * 20 pixel/grid = 50 pixel (max). Cal vison_range based on %valve_open_status
        user_data.curr_vision_range = (50.0f * valve_data.valve_open_status) / 100.0f;
    }
    else
    {
        // Spray Mode
        user_data.curr_view_cone_angle = 60.0f;
        // 1.5 grid * 20 pixel/grid = 30 pixel (max). Cal vison_range based on %valve_open_status
        user_data.curr_vision_range = (30.0f * valve_data.valve_open_status) / 100.0f;
    }

    if (user_data.curr_vision_range > 0)
    {
        const int num_segments = 6;
        float total_view_angle_rad = user_data.curr_view_cone_angle * (PI / 180.0f);
        float angle_step = total_view_angle_rad / num_segments;
        float start_angle = user_data.curr_yaw_angle - (total_view_angle_rad / 2.0f);

        int prev_x = cx + round(user_data.curr_vision_range * sin(start_angle));
        int prev_y = cy - round(user_data.curr_vision_range * cos(start_angle));

        // Draw num_segments triangle
        for (int i = 1; i <= num_segments; i++)
        {
            float current_angle = start_angle + (i * angle_step);

            int next_x = cx + round(user_data.curr_vision_range * sin(current_angle));
            int next_y = cy - round(user_data.curr_vision_range * cos(current_angle));

            tft.fillTriangle(cx, cy, prev_x, prev_y, next_x, next_y, USER_VIEW_CONE_COLOR);

            prev_x = next_x;
            prev_y = next_y;
        }
    }
    // Draw user
    tft.fillCircle(cx, cy, 5, BLUE);

    // Save previous position and heading state
    user_data.last_user_x = user_data.user_x;
    user_data.last_user_y = user_data.user_y;
    user_data.prev_yaw_angle = user_data.curr_yaw_angle;
    user_data.prev_vision_range = user_data.curr_vision_range;
    user_data.prev_view_cone_angle = user_data.curr_view_cone_angle;
}

void display_progress_bar(Adafruit_ILI9341 &tft, int x, int y, int width, int height, int percentage)
{
    if (percentage < 0)
        percentage = 0;
    if (percentage > 100)
        percentage = 100;
    // Đổi màu theo progress
    uint16_t color;
    if (percentage <= 33)
    {
        color = RED;
    }
    else if (percentage <= 66)
    {
        color = YELLOW;
    }
    else
    {
        color = GREEN;
    }
    //
    int filled_width = round((percentage * width) / 100);

    // Cập nhật thanh progress
    tft.drawRect(x, y, width, height, STATIC_TEXT_COLOR);
    tft.fillRect(x + 1, y + 1, width - 2, height - 2, BACKGROUND_COLOR);
    tft.fillRect(x + 1, y + 1, filled_width - 2, height - 2, color);
}

void lcd_display_status_data(Adafruit_ILI9341 &tft, User_data &user_data, Valve_Data &valve_data)
{
    // ===================== User score ========================
    String score_str = String(user_data.user_score);

    // X(220->319), Y(35->70)
    tft.fillRect(221, 36, 97, 33, BLACK);
    tft.setTextSize(3);
    tft.setTextColor(WHITE);

    // Font size 3, each character 18px
    int text_width = score_str.length() * 18;
    int cursor_x = 220 + (98 - text_width) / 2;
    int cursor_y = 42;

    tft.setCursor(cursor_x, cursor_y);
    tft.print(score_str);
    display_progress_bar(tft, 220, 98, 100, 30, valve_data.valve_open_status);
}

void lcd_display_reality_mode(Adafruit_ILI9341 &tft, IMU_Data &imu_data, Map_data &map_data, User_data &user_data,
                              Fire_data &fire_data, Valve_Data &valve_data)
{
    lcd_clear_user(tft, map_data, imu_data, valve_data);
    lcd_setup_map_outline(tft);
    lcd_display_status_data(tft, user_data, valve_data);
    if (map_updated)
    {
        Serial.printf("Map updated!\n");
        map_updated = false;
        lcd_clear_map(tft);
        lcd_display_map(tft, map_data);
    }
    else
    {
        lcd_display_map(tft, map_data);
    }

    lcd_display_fire(tft, fire_data);

    lcd_display_user(tft, map_data, user_data, imu_data, valve_data);
}