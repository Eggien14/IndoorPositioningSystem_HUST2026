/*
 * uwb_app.h
 *
 *  Created on: Mar 7, 2026
 *      Author: HaiVuQuang
 *      Github: https://github.com/HaiVuQuang
 *      Email: Hainhatquangvu@gmail.com
 */

#ifndef INC_UWB_APP_H_
#define INC_UWB_APP_H_

#include "main.h"
#include "deca_device_api.h"
#include "deca_param_types.h"
#include "deca_regs.h"
#include "deca_version.h"
#include "uwb_shared_def.h"

#include <stdint.h>
#include <string.h>
#include <stdbool.h>
#include <stdarg.h>
#include "stm32f1xx_hal.h"


/* ================= NODE TYPE CONFIGURATION ================= */
#define TYPE_MASTER 1
#define TYPE_SLAVE  2
#define TYPE_TAG    3

/* >>>>>>>>> !!! CHỌN LOẠI NODE BIÊN DỊCH TẠI ĐÂY !!! <<<<<<<<< */
//#define CURRENT_NODE_TYPE   TYPE_MASTER			// ID từ 0xF0 -> 0xFF (Max: 16)
#define CURRENT_NODE_TYPE   TYPE_SLAVE		// ID từ 0x01 -> 0xCF (Max: 208)
//#define CURRENT_NODE_TYPE   TYPE_TAG			// ID từ 0xD0 -> 0xEF (Max: 32)

//#define MAX_TAGS            5				// Số lượng Tag tối đa hỗ trợ
//#define MAX_SLAVES          7				// Số lượng Slv_Beacon tối đa hỗ trợ
#define MAX_TAGS            3				// Số lượng Tag tối đa hỗ trợ
#define MAX_SLAVES          4				// Số lượng Slv_Beacon tối đa hỗ trợ


//Node define
#if (CURRENT_NODE_TYPE == TYPE_TAG)
// --- Cấu hình ID cho TAG ---
#define MY_TAG_ID	0xD0


#elif (CURRENT_NODE_TYPE == TYPE_SLAVE)
// --- Cấu hình ID cho Slave Beacon ---
#define MY_SLV_BEACON_ID        0x03
#define MY_MST_ID		 		0xF0
#define SLV_EVENT_QUEUE_SIZE 	10

// --- Danh sách các Slave Beacon cùng thuộc quản lý (tương ứng TDMA slot) ---
static const uint8_t SLV_TOPOLOGY_LIST[MAX_SLAVES] = {
    0x01, 0x02, 0x03, 0x04
};


#elif (CURRENT_NODE_TYPE == TYPE_MASTER)

// --- Cấu hình ID cho Master Beacon ---
#define MY_MST_BEACON_ID       0xF0
#define TAG_TTL_MAX             200       // Time to live -> Tag bị xóa nếu ko Response quá 50 chu kỳ
#define MSG_QUEUE_SIZE          10      // Kích thước hàng đợi Ring Buffer cho UART

// --- Danh sách ID các Slave Beacon thuộc quản lý ---
static const uint8_t CONTROL_SLV_LIST[MAX_SLAVES] = {
    0x01, 0x02, 0x03, 0x04
};

#endif


/* ======================= HARDWARE ========================= */
extern TIM_HandleTypeDef htim2;			//Timer 2
extern UART_HandleTypeDef huart1;		//UART1
extern UART_HandleTypeDef huart2;		//UART2


/* =================== THÔNG SỐ HỆ THỐNG ==================== */

// Các trường cố định bản tin
#define FRAME_CONTROL 		0x8841			// Frame control: 0x8841 -> Bản tin dùng địa chỉ 16-bit
#define PAN_ID              0xDECA			// Personal Area Network Identifier -> Lọc các thiết bị chung mạng
#define BROADCAST_ID        0xFFFF			// ID mặc định dùng để Broadcast

// Function Codes
#define FUNC_ADV          	0xA1			// [TAG] Bản tin quảng bá ADV
#define FUNC_MASTER_POLL  	0xA2			// [MST_BEACON] Bản tin Master Beacon POLL
#define FUNC_SLAVE_POLL   	0xA3			// [SLV_BEACON] Bản tin Slave Beacon POLL
#define FUNC_TAG_RESP     	0xA4			// [TAG] Bản tin Response

// Invalid instance
#define INVALID_DIST        0xFFFF			// Error khi tính toán K/c
#define MAX_DIST_CM			5000			// K/c tối đa cho phép (cm) từ Tag -> Beacon. Y/c bố trí vị trí Beacon hợp lý trong khu vực
											// -> Xa hơn MAX_DIST_CM nguy cơ kết quả đo là NLOS và sai số cao -> Mặc định là INVALID_DIST và ko xử lý tiếp


/* ====================== TDMA Timing ========================
* 	|----------------------------------34ms----------------------------------|
*	|--2--|------------16--------------|--1--|-----------12-------------|--3--|
*	(MST_Poll)		(SLV_Poll)		   (BACKUP)		  (TAG_RES)       (DIST_CAL)
*/

// ============================ FAST SPEED OPTION: 34ms ====================================
#define CYCLE_PERIOD_MS     		34				// Chu kỳ tổng mỗi pha Ranging
#define MASTER_POLL_TIMEOUT			2000
#define SLAVE_POLL_TIMEOUT			17000			// 20ms: (Max tải) + 1ms Backup
#define TAG_RESPONSE_TIMEOUT		12000			// 15ms: (Max tải)
#define DIST_CAL_TIMEOUT			3000			// 4ms:	Slv_Beacon tính toán k/c pha hiện tại

#define SLAVE_TDMA_BASE_US  		2000  			// Slv_Beacon đầu tiên bắt đầu sau 4 ms từ đầu chu kỳ hiện tại
#define SLAVE_SLOT_TDMA_US  		4000  			// Mỗi Slv_Beacon cách nhau 4 ms
#define TAG_TDMA_BASE_US    		19000 			// Tag đầu tiên bắt đầu sau 26 ms từ đầu chu kỳ hiện tại
#define TAG_SLOT_TDMA_US    		4000  			// Mỗi Tag cách nhau 3ms

// System Timeout
#define ADV_CYCLE_MS 				300 			// Khoảng cách giữa các gói ADV (ms)
#define WAIT_MST_POLL_TIMEOUT_MS	500				// Timeout đợt Mst Poll (ms)


/* =================== CẤU TRÚC BẢN TIN  =================== */
#define MAC_HDR_LEN 				9				// Độ dài MAC Header theo IEEE 802.15.4
#define FCS_LEN						2				// Độ dài Frame Control Sequence

#pragma pack(push, 1)

// --- Cấu trúc bản tin chuẩn IEEE 802.15.4 (9 bytes MAC header + Payload + 2 bytes FCS) ---
typedef struct {

    // IEEE 802.15.4 Header (MHR)
    uint16_t frame_ctrl;				// Frame control
    uint8_t  seq_num;					// Sequence number
    uint16_t pan_id;					// Personal Area Network Identifier
    uint16_t dest_addr;					// Địa chỉ nguồn 16-bit
    uint16_t src_addr;					// Địa chỉ đích 16-bit

    // UWB Payload + FCS
    uint8_t	payload[64];
} uwb_msg_frame_t;


// --- Tag ADV Payload ---
//	[ Header | Func | TagID ]
typedef struct {
    uint8_t func_code;    				// FUNC_ADV: 0xA1
    uint8_t tag_id;       				// Tag ID
} pkt_adv_t;


// --- Mst_Beacon Poll Payload ---
typedef struct {
    uint8_t func_code;    				// FUNC_MASTER_POLL: 0xA2
    uint8_t mst_id;						// ID MST_beacon
    uint8_t tag_count;    				// Số lượng Tag tham gia
    uint8_t tag_ids[MAX_TAGS]; 			// Danh sách ID
} pkt_master_poll_t;


// Struct phụ cho Slv_Beacon Poll
typedef struct {
    uint8_t tag_id;						// ID Tag
    uint16_t dist_cm;					// Khoảng cách với Tag đó
    									// Max 65536 cm ~ 655.36 m
} tag_dist_t;


// --- Slv_Beacon Poll Payload ---
typedef struct {
	uint8_t func_code;					// FUNC_SLAVE_POL: 0xA3
	uint8_t slv_id;						// Slv_beacon ID
	uint8_t tag_count;    				// Số lượng Tag tham gia
	tag_dist_t distances[MAX_TAGS];		// Array quản lý k/c đo được với các Tag
} pkt_slave_poll_t;


// Struct phụ cho Tag Response
typedef struct {
    uint8_t slv_beacon_id;				// Beacon ID
    uint32_t poll_rx_ts;  				// Timestamp Tag nhận được gói Poll của Beacon này
} rx_info_t;


// --- Tag Response Payload ---
typedef struct {
    uint8_t func_code;    				// FUNC_TAG_RESP: 0xA4
    uint8_t tag_id;						// Tag ID
    uint32_t resp_tx_ts;  				// Thời gian Tag dự kiến gửi gói này
    uint8_t beacon_count; 				// Số lượng thông tin Beacon đính kèm
    rx_info_t rx_infos[MAX_SLAVES + 1]; // +1 vì tính cả Master
} pkt_tag_resp_t;

#pragma pack(pop)

/* =================== GLOBAL FUNCTION  =================== */
extern uwb_dev_config_t uwb_cfg;

void Reset_DW1000(void);

void port_set_dw1000_slowrate(SPI_HandleTypeDef *hspi);

void port_set_dw1000_fastrate(SPI_HandleTypeDef *hspi);

uint64_t get_rx_timestamp_u64(void);

uint64_t get_sys_timestamp_u64(void);

void debug_print(const char *format, ...);

void send_to_centralMCU(uint8_t *pData, uint16_t Size);

/* =================== NODE FUNCTION  =================== */

#if (CURRENT_NODE_TYPE == TYPE_TAG)

	void tag_loop(void);

	void tag_rx_handler(uwb_msg_frame_t *rx_frame, uint8_t func_code);

#elif (CURRENT_NODE_TYPE == TYPE_SLAVE)

	 void slv_beacon_init(void);

	void slv_beacon_loop(void);

	void slv_rx_handler(uwb_msg_frame_t *rx_frame, uint8_t func_code);

#elif (CURRENT_NODE_TYPE == TYPE_MASTER)

	void mst_beacon_init(void);

	void mst_beacon_loop(void);

	void mst_rx_handler(uwb_msg_frame_t *rx_frame, uint8_t func_code);

#endif

#endif /* INC_UWB_APP_H_ */
