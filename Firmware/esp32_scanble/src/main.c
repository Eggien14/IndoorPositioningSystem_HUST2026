#include "config.h"
#include "ble_handle.h"

void app_main()
{
    ble_init();
    uart_init();

    while (1)
    {
       vTaskDelay(pdMS_TO_TICKS(10));
    }
}