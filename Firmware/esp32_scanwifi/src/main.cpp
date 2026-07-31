#include <WiFi.h>

// Define UART pin
#define RXD2 16
#define TXD2 17

// Channel be scaned 
#define CHANNEL 6

// SSID of target access point
// const char *target_ssid[4] = {"RSSI1", "RSSI2", "RSSI3", "RSSI4"};
// MAC address of target access point
const char *target_mac[4] = {
    "F4:83:CD:F0:8A:C4",
    "F4:83:CD:77:40:80",
    "34:96:72:EA:28:F0",
    "E8:48:B8:95:4D:4F"
};
// ID of target access point
const int id[4] = {1, 2, 3, 4};

#define SCAN_TIME_MS 30 // Times scan 1 channel wifi

unsigned long lasttime = 0;
int rssi_count = 0;

// Check SSID function
// int check_ssid(const char *ssid, int i)
// {
//   if (strcmp(ssid, target_ssid[i - 1]) == 0)
//     return id[i - 1];
//   return 0;
// }

// Check MAC function
int check_mac(const char *mac, int i)
{
  if (strcmp(mac, target_mac[i - 1]) == 0)
    return id[i - 1];
  return 0;
}

void send_data(int id, int rssi)
{
  char buffer[50];
  sprintf(buffer, "%d %d", id, rssi);
  Serial2.println(buffer);
}

void setup()
{
  Serial.begin(115200);
  Serial2.begin(115200, SERIAL_8N1, RXD2, TXD2);
  WiFi.mode(WIFI_STA);
  WiFi.disconnect();
  delay(100);

  Serial.println("Start scanning WiFi...");
}

void loop()
{
  int a = WiFi.scanNetworks(false, false, false, SCAN_TIME_MS, CHANNEL, nullptr, nullptr);
  if (a > 0)
  {
    for (int j = 0; j < a; j++)
    {
      for (int i = 1; i <= 4; i++)
      {
        // int id = check_ssid((char *)WiFi.SSID(j).c_str(), i);
        int id = check_mac(WiFi.BSSIDstr(j).c_str(), i);
        if (id != 0)
        {
          rssi_count++;
          send_data(id, WiFi.RSSI(j));
        }
      }
    }
  }
  WiFi.scanDelete();
}
