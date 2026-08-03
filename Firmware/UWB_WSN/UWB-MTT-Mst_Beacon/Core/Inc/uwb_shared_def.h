/*
 * uwb_shared_def.h
 *
 *  Created on: Mar 7, 2026
 *      Author: ADMIN
 */

#ifndef INC_UWB_SHARED_DEF_H_
#define INC_UWB_SHARED_DEF_H_

#include <stdint.h>

/* ================= THÔNG SỐ PHẦN CỨNG UWB ================= */

/* Channel number */
#define CHANNEL_NUM 2
//#define CHANNEL_NUM 4

/* Default antenna delay values for 64 MHz PRF*/
// MST 0xF0
#define TX_ANT_DLY 16514
#define RX_ANT_DLY 16514

/* UWB microsecond (uus) to device time unit (dtu, around 15.65 ps) conversion factor.
 * 1 uus = 512 / 499.2 �s and 1 �s = 499.2 * 128 dtu. */
#define UUS_TO_DWT_TIME 65536

/* Delay between frames, in UWB microseconds.*/
#define POLL_RX_TO_RESP_TX_DLY_UUS 5000

/* Delay between frames, in UWB microseconds. */
#define POLL_TX_TO_RESP_RX_DLY_UUS 330

/* Speed of light in air (m/s) */
#define SPEED_OF_LIGHT 299702547

// Multiplication factors to convert carrier integrator value to a frequency offset in Hertz
#define FREQ_OFFSET_MULTIPLIER          (998.4e6/2.0/1024.0/131072.0)
#define FREQ_OFFSET_MULTIPLIER_110KB    (998.4e6/2.0/8192.0/131072.0)

// Multiplication factors to convert frequency offset in Hertz to PPM crystal offset
// NB: also changes sign so a positive value means the local RX clock is running slower than the remote TX device.
#define HERTZ_TO_PPM_MULTIPLIER_CHAN_1     (-1.0e6/3494.4e6)
#define HERTZ_TO_PPM_MULTIPLIER_CHAN_2     (-1.0e6/3993.6e6)	// Channel 4 cũng dùng được do cùng central frequency
#define HERTZ_TO_PPM_MULTIPLIER_CHAN_3     (-1.0e6/4492.8e6)
#define HERTZ_TO_PPM_MULTIPLIER_CHAN_5     (-1.0e6/6489.6e6)	// Channel 7 cũng dùng được do cùng central frequency

/* UWB communication config struct */
typedef struct {
    uint16_t short_addr;
    uint16_t ant_dly_tx;
    uint16_t ant_dly_rx;
    dwt_config_t config;
    dwt_txconfig_t tx_config;
} uwb_dev_config_t;


/* ================= THÔNG SỐ HỆ THỐNG ================= */

/* --- Communication specifications ---*/
/* Length of the common part of the message (up to and including the function code)*/
#define ALL_MSG_COMMON_LEN 10

/* Indexes to access some of the fields in the frames defined above. */
#define ALL_MSG_SN_IDX 2						//Identify duplicate message
#define RESP_MSG_POLL_RX_TS_IDX 10
#define RESP_MSG_RESP_TX_TS_IDX 14
#define RESP_MSG_TS_LEN 4

/* Its size is adjusted to longest frame that this example code is supposed to handle. */
#define RX_BUF_LEN 128

/* Receive response timeout.*/
#define RESP_RX_TIMEOUT_UUS 6000

#endif /* INC_UWB_SHARED_DEF_H_ */
