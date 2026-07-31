#include "services/read_valve.h"

void init_valve(void)
{
    pinMode(VALVE_STATUS_PIN, INPUT);
    pinMode(VALVE_MODE_PIN, INPUT);
}
void read_valve(Valve_Data *valve_data)
{
    int raw_valve_status = analogRead(VALVE_STATUS_PIN);
    int raw_valve_mode = analogRead(VALVE_MODE_PIN);

    // Convert ADC value to opening percentage
    valve_data->valve_open_status = (int)((raw_valve_status / 700.0) * 100);
    valve_data->mode_status = (int)((raw_valve_mode / 700.0) * 100);

}
