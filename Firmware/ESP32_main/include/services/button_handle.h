#ifndef BUTTON_HANDLER_H
#define BUTTON_HANDLER_H

#include "config.h"

void init_button(void); // Initialize GPIO pins for buttons and analog inputs
// Check mode of system:
bool is_sw2_on(void); // True for Training mode and False for Reality Mode

bool is_sw1_on(void); // True for Training/Reality Mode and False for Default Mode

#endif // BUTTON_HANDLER_H