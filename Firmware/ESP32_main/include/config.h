#ifndef CONFIG_H
#define CONFIG_H

#include <vector>

#include <Arduino.h>
#include <stdio.h>
#include <Wire.h>
#include <SPI.h>
#include <wifi.h>
#include <PubSubClient.h>
#include <Adafruit_GFX.h>
#include <Adafruit_ILI9341.h>
#include <ArduinoJson.h>

// Device ID and mode of system
/*#############################################################################################################*/

// Device ID
#define DEVICE_ID 14 // Device ID for MQTT

// Device Name
#define DEVICE_NAME "Fire steering"

// Mode of system
enum ModeSystem
{
    DEFAULT_MODE,  // Default mode of system (Sending Information, Training/Reality Topic)
    TRAINING_MODE, // Training mode (Sending data)
    REALITY_MODE   // Reality mode (Sending data and valve/mode of extinguish status)
};
// #define DEFAULT_MODE 0  // Default mode of system (Sending Information, Training/Reality Topic)
// #define TRAINING_MODE 1 // Training mode (Sending data and counter)
// #define REALITY_MODE 2  // Reality mode (Sending data and valve/mode of extinguish status)

// Link youtube for turtorial
#define YOUTUBE_LINK "https://youtu.be/BHWp2Lj1LJE"

// QR code
/*To convert QR code to array in C++, run "C:\Users\Admin\Project\other\qr_code_to_cpp_byte.py"
with link of .png QR code file and copy the output to here*/
#define QR_SIZE 31
const uint8_t DEMO_QR[QR_SIZE][QR_SIZE] = {
    {0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0},
    {0, 1, 1, 1, 1, 1, 1, 1, 0, 1, 1, 1, 0, 1, 0, 0, 0, 0, 1, 1, 1, 0, 0, 1, 1, 1, 1, 1, 1, 1, 0},
    {0, 1, 0, 0, 0, 0, 0, 1, 0, 1, 1, 1, 0, 0, 0, 0, 0, 1, 0, 0, 1, 1, 0, 1, 0, 0, 0, 0, 0, 1, 0},
    {0, 1, 0, 1, 1, 1, 0, 1, 0, 1, 0, 1, 1, 0, 1, 0, 1, 1, 1, 0, 1, 0, 0, 1, 0, 1, 1, 1, 0, 1, 0},
    {0, 1, 0, 1, 1, 1, 0, 1, 0, 1, 1, 0, 1, 0, 0, 1, 1, 1, 0, 1, 0, 1, 0, 1, 0, 1, 1, 1, 0, 1, 0},
    {0, 1, 0, 1, 1, 1, 0, 1, 0, 0, 0, 0, 0, 0, 1, 1, 0, 1, 1, 1, 0, 1, 0, 1, 0, 1, 1, 1, 0, 1, 0},
    {0, 1, 0, 0, 0, 0, 0, 1, 0, 1, 0, 0, 1, 1, 1, 1, 1, 0, 1, 1, 1, 1, 0, 1, 0, 0, 0, 0, 0, 1, 0},
    {0, 1, 1, 1, 1, 1, 1, 1, 0, 1, 0, 1, 0, 1, 0, 1, 0, 1, 0, 1, 0, 1, 0, 1, 1, 1, 1, 1, 1, 1, 0},
    {0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 1, 0, 1, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0},
    {0, 1, 1, 0, 0, 1, 1, 1, 0, 0, 0, 0, 1, 0, 1, 1, 1, 1, 1, 1, 1, 0, 0, 0, 1, 0, 1, 1, 1, 1, 0},
    {0, 0, 0, 0, 1, 1, 1, 0, 0, 0, 1, 1, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 1, 1, 1, 1, 0},
    {0, 0, 1, 0, 0, 1, 0, 1, 1, 0, 0, 0, 1, 1, 1, 1, 1, 0, 1, 0, 0, 1, 0, 1, 1, 0, 0, 0, 0, 1, 0},
    {0, 0, 1, 0, 0, 1, 1, 0, 0, 1, 0, 1, 1, 0, 1, 0, 1, 1, 1, 1, 1, 1, 0, 1, 0, 0, 1, 0, 1, 1, 0},
    {0, 0, 0, 0, 0, 0, 0, 1, 1, 1, 0, 1, 0, 1, 1, 0, 0, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0},
    {0, 1, 0, 1, 0, 0, 1, 0, 1, 1, 0, 0, 0, 0, 1, 1, 0, 1, 1, 1, 1, 0, 0, 1, 1, 1, 1, 1, 1, 1, 0},
    {0, 1, 1, 1, 1, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 1, 0, 0, 0, 0, 0, 0, 1, 1, 0, 1, 0},
    {0, 0, 1, 0, 1, 1, 0, 0, 0, 1, 1, 1, 0, 1, 0, 1, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0, 0, 0, 1, 1, 0},
    {0, 0, 1, 0, 1, 0, 1, 1, 1, 1, 1, 0, 1, 0, 1, 1, 1, 1, 0, 0, 0, 1, 1, 0, 1, 0, 0, 0, 1, 0, 0},
    {0, 1, 0, 0, 1, 0, 0, 0, 1, 0, 0, 1, 0, 1, 0, 0, 0, 0, 1, 1, 1, 0, 0, 1, 1, 1, 1, 0, 1, 1, 0},
    {0, 0, 0, 0, 1, 1, 1, 1, 1, 1, 0, 0, 1, 1, 1, 1, 1, 0, 0, 0, 0, 0, 1, 1, 0, 1, 0, 1, 0, 1, 0},
    {0, 0, 0, 1, 0, 0, 1, 0, 0, 0, 0, 1, 1, 0, 1, 0, 1, 1, 1, 0, 1, 0, 1, 0, 0, 1, 0, 0, 1, 1, 0},
    {0, 1, 1, 1, 0, 1, 0, 1, 0, 1, 0, 0, 0, 1, 1, 0, 0, 0, 0, 0, 1, 1, 1, 1, 1, 1, 1, 0, 0, 1, 0},
    {0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 1, 0, 0, 1, 1, 0, 1, 0, 1, 1, 1, 0, 0, 0, 1, 0, 0, 0, 1, 0},
    {0, 1, 1, 1, 1, 1, 1, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 1, 0, 1, 0, 1, 0, 1, 1, 1, 0, 1, 0},
    {0, 1, 0, 0, 0, 0, 0, 1, 0, 1, 0, 1, 0, 1, 0, 1, 0, 0, 1, 1, 1, 1, 0, 0, 0, 1, 0, 0, 1, 1, 0},
    {0, 1, 0, 1, 1, 1, 0, 1, 0, 1, 1, 1, 1, 0, 1, 1, 1, 1, 0, 1, 1, 1, 1, 1, 1, 1, 1, 0, 1, 1, 0},
    {0, 1, 0, 1, 1, 1, 0, 1, 0, 0, 1, 0, 0, 1, 0, 0, 0, 0, 1, 1, 0, 0, 1, 0, 0, 0, 0, 0, 1, 0, 0},
    {0, 1, 0, 1, 1, 1, 0, 1, 0, 0, 1, 0, 1, 1, 1, 1, 1, 0, 0, 1, 1, 1, 1, 0, 0, 0, 1, 1, 1, 1, 0},
    {0, 1, 0, 0, 0, 0, 0, 1, 0, 1, 0, 0, 1, 0, 1, 0, 1, 1, 0, 0, 0, 1, 0, 1, 0, 0, 1, 0, 1, 1, 0},
    {0, 1, 1, 1, 1, 1, 1, 1, 0, 1, 1, 1, 0, 1, 1, 0, 0, 0, 0, 0, 1, 1, 1, 0, 0, 0, 0, 0, 1, 0, 0},
    {0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0},
};

// Debug Configuration
/*#############################################################################################################*/

// Serial Monitor Settings
#define BAUD_RATE_SERIAL 115200 // Serial monitor baud rate (bps)
#define DEBUG_INTERVAL 1000     // Debug print interval (ms)

/*#############################################################################################################*/

// UART Configuration for 2 ESP32
/*#############################################################################################################*/

// UART Pin Definitions
#define UART_TX_PIN_ESP_WIFI 17 // TX pin (GPIO17)
#define UART_RX_PIN_ESP_WIFI 16 // RX pin (GPIO16)

#define UART_TX_PIN_ESP_BLE 26 // TX pin (GPIO26)
#define UART_RX_PIN_ESP_BLE 25 // RX pin (GPIO25)

// UART Communication Settings
#define UART_ID_ESP_WIFI 1 // UART2 peripheral
#define UART_ID_ESP_BLE 2  // UART1 peripheral

#define BAUD_RATE_ESP_WIFI 115200 // Must match Pi Pico's baud rate
#define BAUD_RATE_ESP_BLE 115200

/*#############################################################################################################*/

// I2C Configuration for reading data from BNO055, and BNO055 setup
/*#############################################################################################################*/

// BNO055 I2C Configuration
#define I2C_SDA 21             // Default SDA pin for ESP32
#define I2C_SCL 22             // Default SCL pin for ESP32
#define BNO055_EX_ADDRESS 0x28 // Default I2C address for BNO055
#define BNO055_IN_ADDRESS 0x29 // Alternative I2C address for BNO055 (if ADR pin is high)

// BNO055 Register Addresses
#define ACC_DATA_START 0x28        // Accelerometer data registers 0x08-0x0D
#define MAG_DATA_START 0x0E        // Magnetometer data registers
#define GYRO_DATA_START 0x14       // Gyroscope data registers
#define EULER_DATA_START 0x1A      // Euler angles data registers
#define QUATERNION_DATA_START 0x20 // Quaternion data registers

// BNO055 Operation Mode Registers
#define BNO055_OPR_MODE_ADDR 0x3D // Operation mode register address
#define BNO055_MODE_CONFIG 0x00   // Configuration mode
#define BNO055_MODE_NDOF 0x0C     // Nine Degrees of Freedom fusion mode

// BNO055 Operation Delays
#define BNO055_CONFIG_DELAY 100 // Delay after changing modes (ms)

// BNO055 Calibration Status Register
#define BNO055_CALIB_STAT_ADDR 0x35 // Calibration status register
#define BNO055_CALIB_STAT_MASK 0xFF // Mask for all calibration status bits

// BNO055 System Status Register
#define BNO055_SYS_STATUS_ADDR 0x39    // System status register
#define BNO055_SYS_STATUS_RUNNING 0x05 // System status: running normally

// BNO055 Error Status Register
#define BNO055_SYS_ERR_ADDR 0x3A // System error status register

/*#############################################################################################################*/

// SPI Configuration for LCD ILI9341, and LCD setup
/*#############################################################################################################*/

// SPI show screen
#define TFT_MISO 19 // SDO - MASTER IN SLAVE OUT (MISO) : Not used, as TFT is write-only
#define TFT_LED 0   // LED : Control LCD backlight connects to 3.3V (could use PWM)
#define TFT_SCK 18  // SCK - CLK : Serial Clock (IMPORTANT)
#define TFT_MOSI 23 // SDI - MASTER OUT SLAVE IN (MOSI) : Serial Data Input (IMPORTANT)
#define TFT_DC 2    // DC : Data/Command control pin (IMPORTANT)
#define TFT_RST 4   // RST - RESET : Reset pin (IMPORTANT)
#define TFT_CS 5    // CS : Chip Select (IMPORTANT)

// LCD setup
#define INTRO_TIME 5000                   // LCD intro time
#define LCD_ROTATION 1                    // LCD rotation
#define LCD_REFRESH_RATE_TRAINING_MODE 10 // LCD refresh rate for training mode (Hz)
#define LCD_REFRESH_RATE_REALITY_MODE 10  // LCD refresh rate for reality mode (Hz)

/*#############################################################################################################*/

// Button Configuration
/*#############################################################################################################*/

// Button Pins
#define MODE_SWITCH_PIN 32 // Training/Reality mode switch
#define TRANS_PIN 33       // Chuyen doi tu default sang hai che do con lai

// Analog Input Pins
#define VALVE_STATUS_PIN 34 // Valve control analog input in reality mode
#define VALVE_MODE_PIN 35   // Mode control analog input in reality mode

// System Modes
#define MODE_REALITY 0  // Reality mode
#define MODE_TRAINING 1 // Training mode

// Analog Thresholds
#define ANALOG_THRESHOLD 2048 // Threshold for analog reading (4096/2)

/*#############################################################################################################*/

// WiFi and MQTT Configuration
/*#############################################################################################################*/

// WiFi Settings
#define WIFI_SSID "RSSI1"
#define WIFI_PASSWORD "11111111"
#define WIFI_TIMEOUT 10000 // Connection timeout (ms)

// MQTT Broker Settings
#define MQTT_BROKER "192.168.0.102"
#define MQTT_PORT 1883 // Default MQTT port
#define MQTT_USERNAME ""
#define MQTT_PASSWORD ""
#define MQTT_CLIENT_ID "ESP32_CLIENT_ID_14"

// MQTT Topics
#define MQTT_DEVICE_INFOR_TOPIC "device_info"
#define MQTT_TRAINING_TOPIC "training_id/14"
#define MQTT_REALITY_TOPIC "reality_id/14"

// Message Publishing Configuration
#define PUBLISH_INTERVAL 50 // Minimum time between messages (ms)

/*#############################################################################################################*/
using namespace std;

#define MAP_WIDTH_MAX 10
#define MAP_HEIGHT_MAX 10

// RSSI_Data defines
/*#############################################################################################################*/

// RSSI_Data struct
typedef struct RSSI_Data
{
    String ssid;
    int ssid_id;
    int rssi;
    unsigned long last_receive_time;
} RSSI_Data;

// RSSI_Timeout defines
#define RSSI_Timeout 3000 // RSSI timeout (ms)

/*#############################################################################################################*/

// IMU_Data defines
/*#############################################################################################################*/

// Quarternion struct
struct Raw_quaternion
{
    int16_t w, x, y, z;
};
struct Real_quaternion
{
    float w, x, y, z;
};

// Vector3 struct
struct Raw_vector3
{
    int16_t x, y, z;
};
struct Real_vector3
{
    float x, y, z;
};

// IMU raw data defines
struct IMU_Raw_Data
{
    Raw_vector3 acc_raw;
    Raw_vector3 mag_raw;
    Raw_vector3 gyro_raw;
    Raw_vector3 euler_raw;
    Raw_quaternion quaternion_raw;
};

// IMU real local data defines
struct IMU_Real_local_Data
{
    Real_vector3 acc_local_real;
    Real_vector3 mag_local_real;
    Real_vector3 gyro_local_real;
    Real_vector3 euler_real;
    Real_quaternion quaternion_real;
};

// IMU real global data defines
struct IMU_Data
{
    Real_vector3 gyro;
    Real_vector3 mag;
    Real_vector3 acc;
    Real_vector3 euler;
};

/*#############################################################################################################*/

// Colour define for LCD
/*############################################################################################################*/

#define BLUE 0x001F
#define WHITE 0xFFFF
#define BLACK 0x0000
#define GREEN 0x07E0
#define YELLOW 0xFFE0
#define ORANGE 0xFD20
#define RED 0xF800
#define DARK_RED 0x8800

/*#############################################################################################################*/

// LCD algorithms variables define
/*#############################################################################################################*/

// Tọa độ xử lý map_grid
struct int_Coordinate
{
    int x, y;
};

typedef struct Valve_Data
{
    int valve_open_status; // 0-100%
    int mode_status;       // 0-100%
} Valve_Data;

typedef struct Map_data
{
    int width;
    int height;
    int map_cells[MAP_WIDTH_MAX][MAP_HEIGHT_MAX];
    int north_offset;
} Map_data;

typedef struct User_data
{
    float last_user_x;
    float last_user_y;
    float user_x;
    float user_y;
    int user_score;
    float curr_yaw_angle; // User current yaw angle
    float prev_yaw_angle; // User previous yaw angle
    // User vision range (Fire's impact range)
    float curr_vision_range;
    float prev_vision_range;

    // User's POV (Fire's impact angle)
    float curr_view_cone_angle;
    float prev_view_cone_angle;
} User_data;
extern bool user_updated;

typedef struct Fire_data
{
    int fire_map[MAP_WIDTH_MAX][MAP_HEIGHT_MAX];
    int fire_num;
} Fire_data;
extern bool fire_updated;

// Color for fire level
const uint16_t fire_color[6] = {
    BLACK,  // lv0
    0xF800, // lv1
    0xFFF0, // lv2
    0xFD04, // lv3
    0xA984, // lv4
    0xA804  // lv5
};

#define BACKGROUND_COLOR 0x0000     // Black
#define USER_DOT_COLOR 0x001F       // Blue
#define USER_VIEW_CONE_COLOR 0x07E0 // Green
#define MAP_GRID_COLOR 0xFFFF       // White
#define NOT_MAP_GRID_COLOR 0x001F   // Blue
#define STATIC_TEXT_COLOR 0xFFFF    // White
/*#############################################################################################################*/

#endif