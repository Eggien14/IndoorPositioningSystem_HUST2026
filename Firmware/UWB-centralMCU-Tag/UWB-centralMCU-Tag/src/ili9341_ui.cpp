#include "ili9341_ui.h"

/*--------------------------------------------------------------------------------------------------------*/
/**
 * @brief Draw progress bar
 */
/*--------------------------------------------------------------------------------------------------------*/
static void draw_progress_bar(Adafruit_ILI9341 &tft, int x, int y, int width, int height, int percentage)
{
    if (percentage < 0)
        percentage = 0;
    if (percentage > 100)
        percentage = 100;
    // Đổi màu theo progress
    uint16_t color;
    if (percentage <= 33)
    {
        color = RED; // Đỏ
    }
    else if (percentage <= 66)
    {
        color = YELLOW; // Vàng
    }
    else
    {
        color = GREEN; // Xanh lá
    }
    //
    int filled_width = round((percentage * width) / 100);

    // Cập nhật thanh progress
    tft.drawRect(x, y, width, height, STATIC_TEXT_COLOR);
    tft.fillRect(x + 1, y + 1, width - 2, height - 2, BACKGROUND_COLOR);
    tft.fillRect(x + 1, y + 1, filled_width - 2, height - 2, color);
}


/*--------------------------------------------------------------------------------------------------------*/
/**
 * @brief Setup map axes outline
 */
/*--------------------------------------------------------------------------------------------------------*/
void tft_setup_map_axes_outline(Adafruit_ILI9341 &tft)
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


/*--------------------------------------------------------------------------------------------------------*/
/**
 * @brief Setup static text 
 */
/*--------------------------------------------------------------------------------------------------------*/
void tft_setup_static_text_outline(Adafruit_ILI9341 &tft)
{
    tft.setTextColor(STATIC_TEXT_COLOR);
    tft.setTextSize(1);
    tft.setCursor(26, 5);
    tft.println("- Firefighting Map layout -");

    // Setup text tĩnh
    tft.setCursor(220, 5);
    tft.println("Device Id:");
    tft.setCursor(286, 5);
    tft.println(MY_DEVICE_ID);
    tft.setCursor(240, 24);
    tft.println("User score");
    tft.setCursor(220, 85);
    tft.println("Valve Opening:");
    tft.setCursor(220, 133);
    tft.println("User position:");
    tft.setCursor(220, 146);
    tft.println("- X:");
    tft.setCursor(220, 159);
    tft.println("- Y:");
    tft.setCursor(220, 179);
    tft.println("User speed:");
    tft.setCursor(220, 199);
    tft.println("Connection state:");
    tft.setCursor(220, 212);
    tft.println("- WiFi: OK");
    tft.setCursor(220, 225);
    tft.println("- UWB: OK");
 
    // Bảng User score
    tft.drawFastVLine(220, 21, 49, STATIC_TEXT_COLOR);
    tft.drawFastVLine(319, 21, 49, STATIC_TEXT_COLOR);
    tft.drawFastHLine(220, 21, 99, STATIC_TEXT_COLOR);
    tft.drawFastHLine(220, 35, 99, STATIC_TEXT_COLOR);
    tft.drawFastHLine(220, 70, 99, STATIC_TEXT_COLOR);
    tft.drawFastHLine(220, 78, 99, STATIC_TEXT_COLOR);
}


/*--------------------------------------------------------------------------------------------------------*/
/**
 * @brief: Setup Static UI
 */
/*--------------------------------------------------------------------------------------------------------*/
void tft_setup_static_ui(Adafruit_ILI9341 &tft)
{
    tft_setup_map_axes_outline(tft);
    tft_setup_static_text_outline(tft);
}


/*--------------------------------------------------------------------------------------------------------*/
/**
 * @brief Update Score, speed, current pos, imu data, valve data
 */
/*--------------------------------------------------------------------------------------------------------*/
void tft_update_device_info_text(Adafruit_ILI9341 &tft, UserDisplay &user, IMU_Data &imu_data, Valve_Data &valve_data)
{
    // ===================== User score ========================
    String score_str = String(user.getScore());

    // X(220->319), Y(35->70)
    tft.fillRect(221, 36, 97, 33, BACKGROUND_COLOR);
    tft.setTextSize(3); 
    tft.setTextColor(WHITE);

    // Font size 3, each character 18px
    int text_width = score_str.length() * 18;
    int cursor_x = 220 + (98 - text_width) / 2;
    int cursor_y = 42;

    tft.setCursor(cursor_x, cursor_y);
    tft.print(score_str);

    // =================== Speed & position ========================
    tft.setTextSize(1);
    tft.setTextColor(WHITE);

    // Delete old position coordinate
    tft.fillRect(246, 146, 30, 8, BACKGROUND_COLOR); 
    tft.fillRect(246, 159, 30, 8, BACKGROUND_COLOR);

    // Draw new position coordinate
    tft.setCursor(247, 146);
    tft.print(user.getCoorX(), 1); 
    tft.setCursor(247, 159);
    tft.print(user.getCoorY(), 1);

    // Update user speed
    tft.fillRect(285, 179, 30, 8, BACKGROUND_COLOR);
    tft.setCursor(285, 179);
    tft.print(user.getSpeed(), 2);

    // ================== Valve open status ========================
    draw_progress_bar(tft, 220, 98, 100, 30, valve_data.valve_open_status);
}


/*--------------------------------------------------------------------------------------------------------*/
/**
 * @brief: Render new excercise frame 
 */
/*--------------------------------------------------------------------------------------------------------*/
void tft_render_new_exercise_frame(Adafruit_ILI9341 &tft, UserDisplay &user, FlamesDisplay &flames, MapDisplay &map, IMU_Data &imu_data, Valve_Data &valve_data)
{
    // --- Clear user previous position ---
    user.clearUser(tft);

    // --- Draw map axes ---
    tft_setup_map_axes_outline(tft);

    // --- Update & Draw Map ---
    if (map.hasNewData()) {
        map.clearMap(tft);  
        map.drawMap(tft);   
        map.clearFlag();    
    } else {
        map.drawMap(tft);
    }

    // --- Update & Draw Flame ---
    if (flames.hasNewData()) {
        flames.clearFlames(tft); 
        flames.drawFlames(tft);  
        flames.clearFlag();      
    } else {
        flames.drawFlames(tft);
    }

    // --- Draw User ---
    user.drawUser(tft, map, imu_data, valve_data);
    user.clearFlag();

}


/*--------------------------------------------------------------------------------------------------------*/
/**
 * @brief TFT interface main loop handler
 */
/*--------------------------------------------------------------------------------------------------------*/
void tft_main_loop_handler(Adafruit_ILI9341 &tft, UserDisplay &user, FlamesDisplay &flames, 
                            MapDisplay &map, IMU_Data &imu_data, Valve_Data &valve_data)
{
    // Calculate user speed
    user.calculateSpeed(imu_data);

    // Render User, Flames, Map
    tft_render_new_exercise_frame(tft, user, flames, map, imu_data, valve_data); 

    // Render static device info text
    tft_update_device_info_text(tft, user, imu_data, valve_data);
}