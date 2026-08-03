#ifndef CONFIG_H
#define CONFIG_H

#include <Arduino.h>
#include <Wire.h>
#include <SPI.h>
#include <PubSubClient.h>
#include <Adafruit_GFX.h>
#include <Adafruit_ILI9341.h>
#include <wifi.h>
#include <ArduinoJson.h>

#include <stdio.h>
#include <stdint.h>
#include <stdbool.h>
#include <string.h>
#include <vector>

using namespace std;

// DEVICE SETTING
/*#############################################################################################################*/
#define TYPE_NOZZLE             1
#define TYPE_EXTINGUISHER       2

#define DEVICE_TYPE             TYPE_NOZZLE
// #define DEVICE_TYPE             TYPE_EXTINGUISHER
#define MY_DEVICE_ID            0xC0

#define MY_IPS_ALGO_CODE        2

// SERIAL SETTING
/*#############################################################################################################*/
// Serial Monitor Settings
#define BAUD_RATE_SERIAL 115200 // Serial monitor baud rate (bps)
#define DEBUG_INTERVAL 100      // Debug print interval (ms)


// WIFI AND MQTT CONFIGURATION
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

// Message Publishing Configuration
#define PUBLISH_INTERVAL 100 // Minimum time between messages (ms)


// BNO055 I2C CONFIGURATION & REGISTER ADDRESS
/*#############################################################################################################*/
// BNO055 I2C Configuration
#define I2C_SDA 21                              // Default SDA pin for ESP32
#define I2C_SCL 22                              // Default SCL pin for ESP32
#define INT_BNO055_ADDRESS 0x29                 // I2C address for internal (Onbroad) BNO055
// #define INT_BNO055_ADDRESS 0x28                 // I2C address for internal (Onbroad) BNO055 -> TEST
#define EXT_BNO055_ADDRESS 0x28                 // I2C address for external BNO055

// BNO055 Register Addresses
#define ACC_DATA_START 0x28                     // Accelerometer data registers 0x08-0x0D
#define MAG_DATA_START 0x0E                     // Magnetometer data registers
#define GYRO_DATA_START 0x14                    // Gyroscope data registers
#define EULER_DATA_START 0x1A                   // Euler angles data registers
#define QUATERNION_DATA_START 0x20              // Quaternion data registers

// BNO055 Operation Mode Registers
#define BNO055_OPR_MODE_ADDR 0x3D               // Operation mode register address
#define BNO055_MODE_CONFIG 0x00                 // Configuration mode
#define BNO055_MODE_NDOF 0x0C                   // Nine Degrees of Freedom fusion mode

// BNO055 Operation Delays
#define BNO055_CONFIG_DELAY 100                 // Delay after changing modes (ms)

// BNO055 Calibration Status Register
#define BNO055_CALIB_STAT_ADDR 0x35             // Calibration status register
#define BNO055_CALIB_STAT_MASK 0xFF             // Mask for all calibration status bits

// BNO055 System Status Register
#define BNO055_SYS_STATUS_ADDR 0x39             // System status register
#define BNO055_SYS_STATUS_RUNNING 0x05          // System status: running normally

// BNO055 Error Status Register
#define BNO055_SYS_ERR_ADDR 0x3A                // System error status register


// ILI9341 SPI CONFIGURATION
/*#############################################################################################################*/
// SPI show screen
#define TFT_MISO 19                             // SDO - MASTER IN SLAVE OUT (MISO) : Not used, as TFT is write-only
#define TFT_LED 0                               // LED : Control LCD backlight connects to 3.3V 
#define TFT_SCK 18                              // SCK - CLK : Serial Clock 
#define TFT_MOSI 23                             // SDI - MASTER OUT SLAVE IN (MOSI) : Serial Data Input 
#define TFT_DC 2                                // DC : Data/Command control pin 
#define TFT_RST 4                               // RST - RESET : Reset pin 
#define TFT_CS 5                                // CS : Chip Select 

// LCD setup
#define INTRO_TIME 5000                         // LCD intro time
#define LCD_ROTATION 1                          // LCD rotation
#define LCD_REFRESH_RATE_TRAINING_MODE 10       // LCD refresh rate for training mode (Hz)
#define LCD_REFRESH_RATE_REALITY_MODE 10        // LCD refresh rate for reality mode (Hz)

// Colour define for LCD
#define BLUE                    0x001F
#define WHITE                   0xFFFF
#define BLACK                   0x0000
#define GREEN                   0x07E0
#define YELLOW                  0xFFE0
#define ORANGE                  0xFD20
#define RED                     0xF800
#define DARK_RED                0x8800


#define BACKGROUND_COLOR        0x0000      // Black
#define USER_DOT_COLOR          0x001F      // Blue
#define USER_VIEW_CONE_COLOR    0x07E0      // Green
#define MAP_GRID_COLOR          0xFFFF      // White
#define NOT_MAP_GRID_COLOR      0x001F      // Blue
#define STATIC_TEXT_COLOR       0xFFFF      // White



// BUTTON CONFIGURATION
/*#############################################################################################################*/
// Button Pins
#define MODE_SWITCH_PIN 32                      // Training/Reality mode switch
#define TRANS_PIN 33                            // Mode change

// Analog Input Pins
#define VALVE_PIN 34                            // Valve control analog input in reality mode

#if (DEVICE_TYPE == TYPE_NOZZLE)
#define MODE_PIN 35                             // Mode control analog input in reality mode
#endif
// System Modes
#define MODE_REALITY 0                          // Reality mode
#define MODE_TRAINING 1                         // Training mode

// Analog Thresholds
#define ANALOG_THRESHOLD 2048                   // Threshold for analog reading (4096/2)

#endif