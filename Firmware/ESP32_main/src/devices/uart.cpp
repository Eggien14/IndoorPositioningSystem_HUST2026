#include "devices/uart.h"

void read_uart(HardwareSerial &uart, RSSI_Data *rssi_data)
{
    // Check if data is available on UART
    if (uart.available() > 0)
    {
        // Parse SSID ID and RSSI value from received string
        int ssid_id = uart.parseInt();
        int rssi = uart.parseInt();

        // Validate SSID ID range (1-4) and store data
        if (ssid_id >= 1 && ssid_id <= 4)
        {
            rssi_data[ssid_id - 1].rssi = rssi;                  // Store RSSI value
            rssi_data[ssid_id - 1].last_receive_time = millis(); // Update last receive time
        }
    }
}

void check_last_receive_time(RSSI_Data *rssi_data)
{
    // Get current time
    unsigned long currentMillis = millis();

    // Check each RSSI data entry
    for (int i = 0; i < 4; i++)
    {
        // If timeout exceeded, mark as NOT FOUND
        if (currentMillis - rssi_data[i].last_receive_time > RSSI_Timeout)
        {
            rssi_data[i].rssi = -100; // Set RSSI to NOT FOUND value
        }
    }
}