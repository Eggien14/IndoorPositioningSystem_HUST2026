#ifndef ILI9341_OBJ_H
#define ILI9341_OBJ_H

#include "config.h"
#include "peripheral_handle.h"

/*--------------------------------------------------------------------------------------------------------*/
/**
 * @brief Map UI class
 */
/*--------------------------------------------------------------------------------------------------------*/
class MapDisplay
{
private:
    bool is_map_updated;

    int max_map_x;
    int max_map_y;

    // Lưới 10x10 lưu trạng thái ĐI ĐƯỢC (true) hoặc KHÔNG ĐI ĐƯỢC (false)
    // Truy cập bằng tọa độ Descartes: is_passable[x][y]
    bool is_passable[10][10];

    // Ánh xạ tọa độ Descartes (Góc dưới trái) sang Pixel TFT (Góc trên trái)
    void coordinate_to_topleft_pixel(int x, int y, int &pixel_x, int &pixel_y);

public:
    MapDisplay();
    
    float north_offset; // Đổi sang float để nhận giá trị góc chính xác hơn

    // Flag handle
    bool hasNewData() {return is_map_updated;};
    void clearFlag() {is_map_updated = false;};

    // Update map data
    void updateData(const char *payload);

    // TFT Display handle
    void clearMap(Adafruit_ILI9341 &tft);
    void drawMap(Adafruit_ILI9341 &tft);
};



/*--------------------------------------------------------------------------------------------------------*/
/**
 * @brief User data & interface class
 */
/*--------------------------------------------------------------------------------------------------------*/
class UserDisplay
{
private:
    typedef struct 
    {
        float coor_x, coor_y;               // User absolute coordinate
        int pixel_x, pixel_y;               // User pixel coordinate (mapping for TFT drawing)
    } user_position_t;

    user_position_t prev_pos;               // Previous position 
    user_position_t curr_pos;               // Current position

    float curr_yaw_angle;                   // User current yaw angle
    float prev_yaw_angle;                   // User previous yaw angle

    // static const int vision_range = 28;     // User vision range (Fire's impact range)
    // static const int view_cone_angle = 54;  // User's POV (Fire's impact angle)

    // User vision range (Fire's impact range)
    float curr_vision_range;
    float prev_vision_range;

    // User's POV (Fire's impact angle)  
    float curr_view_cone_angle;
    float prev_view_cone_angle;

    int user_score;                         // User score

    // Velocity 
    float current_vx;
    float current_vy;
    unsigned long last_speed_cal_time;
    float user_speed;

    bool is_user_updated;                   // Updated flag 

    void coordinate_to_pixel_position(float coor_x, float coor_y, int &pixel_x, int &pixel_y);
public:
    // Constructor 
    UserDisplay();

    // Flag handle
    bool hasNewData() {return is_user_updated;};
    void clearFlag() {is_user_updated = false;};

    // Update User data
    void updateData(float coor_x, float coor_y, int score);

    // TFT Display handle
    void clearUser(Adafruit_ILI9341 &tft);
    void drawUser(Adafruit_ILI9341 &tft, MapDisplay &map_instance, IMU_Data &imu_data, Valve_Data &valve_data);
    void calculateSpeed(const IMU_Data &imu_data);

    // User data
    int getScore() const { return user_score; }
    float getCoorX() const { return curr_pos.coor_x; }
    float getCoorY() const { return curr_pos.coor_y; }
    float getSpeed() const { return user_speed; }
};


/*--------------------------------------------------------------------------------------------------------*/
/**
 * @brief Flame data and UI class
 */
/*--------------------------------------------------------------------------------------------------------*/
class FlamesDisplay  
{
private:
    // Max flames appearred
    static const int MAX_FLAMES_ON_SCREEN = 99;

    // Flame properties
    typedef struct 
    {
        int x;
        int y;
        int level;
    } flame_data_t;
    
    // Size of Flame icon
    static const int ICON_WIDTH = 16;
    static const int ICON_HEIGHT = 15;

    // Flame icon bitmap
    static const unsigned char icon_flame[] PROGMEM;

    // Flames lvl color
    const uint16_t flames_lvl_color[6] = {
    BLACK,  // lv0
    0xFFF0, // lv1: 
    0xFE00, // lv2: 
    0xFC00, // lv3: 
    0xF800, // lv4: 
    0xA000  // lv5: 
    };

    // Flames updated flag
    bool is_flames_updated;

    // Flames handle struct
    flame_data_t prev_flames[MAX_FLAMES_ON_SCREEN];
    flame_data_t curr_flames[MAX_FLAMES_ON_SCREEN];
    int prev_fires_num;
    int curr_fires_num;

    // Convert/Maping absolute descartes coordinate to tft pixel coordinate
    void coordinate_to_pixel_position(float coor_x, float coor_y, int &pixel_x, int &pixel_y);

public:
    FlamesDisplay();

    // Flag handle
    bool hasNewData() {return is_flames_updated;};
    void clearFlag() {is_flames_updated = false;};

    // Update Flames data
    void updateData(const char *payload);

    // TFT Display handle
    void clearFlames(Adafruit_ILI9341 &tft);
    void drawFlames(Adafruit_ILI9341 &tft);

};


/*--------------------------------------------------------------------------------------------------------*/
/**
 * @brief Extern TFT class
 */
/*--------------------------------------------------------------------------------------------------------*/
extern UserDisplay user;
extern FlamesDisplay flames;
extern MapDisplay exercise_map;


#endif