#include "services/mqtt_data_handle.h"

Map_data map_data;
Fire_data fire_data;
User_data user_data;

bool map_updated = false;
bool fire_updated = false;
bool user_updated = false;

void reset_map(int a[MAP_WIDTH_MAX][MAP_HEIGHT_MAX])
{
    for (int i = 0; i < MAP_WIDTH_MAX; i++)
    {
        for (int j = 0; j < MAP_HEIGHT_MAX; j++)
        {
            a[i][j] = 0;
        }
    }
}

void handle_map_data_topic(const char *payload)
{
    reset_map(map_data.map_cells);
    JsonDocument doc;
    // Parse JSON
    DeserializationError error = deserializeJson(doc, payload);
    if (error)
    {
        Serial.print("Map_data JSON parse failed: ");
        Serial.println(error.c_str());
        return;
    }
    map_data.width = doc["info"]["x"];
    map_data.height = doc["info"]["y"];
    map_data.north_offset = doc["info"]["north_offset"];
    JsonArray passable_array = doc["cells"];

    for (JsonArray cell : passable_array)
    {
        int_Coordinate coord;
        coord.x = cell[0];
        coord.y = cell[1];
        map_data.map_cells[coord.x][coord.y] = 1; // Mark passable cells in the map
    }
    map_updated = true;
}

void handle_fire_data_topic(const char *payload)
{
    reset_map(fire_data.fire_map);
    JsonDocument doc;
    // Parse JSON
    DeserializationError error = deserializeJson(doc, payload);
    if (error)
    {
        Serial.print("Fire_data JSON parse failed: ");
        Serial.println(error.c_str());
        return;
    }
    fire_data.fire_num = doc["fires_num"];
    JsonArray fires_array = doc["fires"];
    for (JsonObject fire : fires_array)
    {
        int x = fire["x"];
        int y = fire["y"];
        fire_data.fire_map[x][y] = fire["level"];
    }
    fire_updated = true;
}

void handle_user_data_topic(const char *payload)
{
    user_data.last_user_x = user_data.user_x;
    user_data.last_user_y = user_data.user_y;
    JsonDocument doc;
    // Parse JSON
    DeserializationError error = deserializeJson(doc, payload);
    if (error)
    {
        Serial.print("User_data JSON parse failed: ");
        Serial.println(error.c_str());
        return;
    }
    user_data.user_x = doc["x"];
    user_data.user_y = doc["y"];
    user_data.user_score = doc["score"];
    user_updated = true;
}
