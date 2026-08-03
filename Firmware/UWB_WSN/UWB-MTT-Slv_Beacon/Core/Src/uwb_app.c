/*
 * uwb_app.c
 *
 *  Created on: Mar 8, 2026
 *      Author: HaiVuQuang
 *      Github: https://github.com/HaiVuQuang
 *      Email: Hainhatquangvu@gmail.com
 */

#include "uwb_app.h"


/* ======================================================================
 *				   --- HÀM & BIẾN NỘI BỘ DÙNG CHUNG ---
 * =====================================================================*/

/*------------------------------------------------------------------------
 * @brief: 	Flag & Buffer
 -----------------------------------------------------------------------*/
// Buffer và Flag cho USART1 (Debug)
static char debug_dma_buf[256];
static volatile bool is_debug_tx_ready = true;

// Buffer và Flag cho USART2 (Central MCU)
static uint8_t central_dma_buf[256];
static volatile bool is_central_tx_ready = true;
/*------------------------------------------------------------------------
 * @brief: 	UWB configuration manage struct
 * @param: 	none
 -----------------------------------------------------------------------*/
uwb_dev_config_t uwb_cfg = {

	/* Antena Delay Configuration */
    .ant_dly_tx = TX_ANT_DLY,				/* TX antena Delay */
    .ant_dly_rx = RX_ANT_DLY,				/* RX antena Delay */

//    /* RF Configuration */
    .config = {
		.chan = CHANNEL_NUM,				/* Channel number. */
		.prf = DWT_PRF_64M,					/* Pulse repetition frequency. */
		.txPreambLength = DWT_PLEN_128,		/* Preamble length. Used in TX only. */
		.rxPAC = DWT_PAC8,					/* Preamble acquisition chunk size. Used in RX only. */
		.txCode = 9,						/* TX preamble code. Used in TX only. */
		.rxCode = 9,						/* RX preamble code. Used in RX only. */
		.nsSFD = 0,							/* 0 to use standard SFD, 1 to use non-standard SFD. */
		.dataRate = DWT_BR_6M8,				/* Data rate. */
		.phrMode = DWT_PHRMODE_STD,			/* PHY header mode. */
		.sfdTO = (129 + 8 - 8)				/* SFD timeout (preamble length + 1 + SFD length - PAC size). Used in RX only. */
    },

//    .config = {
//		.chan = CHANNEL_NUM,				/* Channel number. */
//		.prf = DWT_PRF_64M,					/* Pulse repetition frequency. */
//		.txPreambLength = DWT_PLEN_256,		/* Preamble length. Used in TX only. */
//		.rxPAC = DWT_PAC16,					/* Preamble acquisition chunk size. Used in RX only. */
//		.txCode = 9,						/* TX preamble code. Used in TX only. */
//		.rxCode = 9,						/* RX preamble code. Used in RX only. */
//		.nsSFD = 0,							/* 0 to use standard SFD, 1 to use non-standard SFD. */
//		.dataRate = DWT_BR_6M8,				/* Data rate. */
//		.phrMode = DWT_PHRMODE_STD,			/* PHY header mode. */
//		.sfdTO = (256 + 1 + 8 - 16)				/* SFD timeout (preamble length + 1 + SFD length - PAC size). Used in RX only. */
//    },

	/* RF Configuration */
//   .config = {
//		.chan = CHANNEL_NUM,				/* Channel number. */
//		.prf = DWT_PRF_64M,					/* Pulse repetition frequency. */
//		.txPreambLength = DWT_PLEN_1024,	/* Preamble length. Used in TX only. */
//		.rxPAC = DWT_PAC32,					/* Preamble acquisition chunk size. Used in RX only. */
//		.txCode = 9,						/* TX preamble code. Used in TX only. */
//		.rxCode = 9,						/* RX preamble code. Used in RX only. */
//		.nsSFD = 0,							/* 0 to use standard SFD, 1 to use non-standard SFD. */
//		.dataRate = DWT_BR_850K,			/* Data rate. */
//		.phrMode = DWT_PHRMODE_STD,			/* PHY header mode. */
//		.sfdTO = (1024 + 1 + 8 - 32)		/* SFD timeout (preamble length + 1 + SFD length - PAC size). Used in RX only. */
//   },

    /* TX Power Configuration */
    .tx_config = {
        .PGdly = 0xC2,       				/* PG Delay cho Channel 2 */
        .power = 0x6C6C6C6C  				/* Công suất phát cho Channel 2 */
    }
//   .tx_config = {
//       .PGdly = 0x95,       				/* PG Delay cho Channel 4 */
//       .power = 0x9A9A9A9A  				/* Công suất phát cho Channel 4 */
//   }
};

/*----------------------------------------------------------------------
 * @brief: 	Reset module DW1000
 * @param: 	none
 *
 ----------------------------------------------------------------------*/
void Reset_DW1000(void) {
    HAL_GPIO_WritePin(DW_RESET_GPIO_Port, DW_RESET_Pin, GPIO_PIN_RESET);
    HAL_Delay(5);
    HAL_GPIO_WritePin(DW_RESET_GPIO_Port, DW_RESET_Pin, GPIO_PIN_SET);
    HAL_Delay(5);
}


/*----------------------------------------------------------------------
 * @brief: 	Set hspi1 clock to 2.25MHz (UWB init)
 * @param: 	none
 *
 ----------------------------------------------------------------------*/
void port_set_dw1000_slowrate(SPI_HandleTypeDef *hspi) {
	hspi->Init.BaudRatePrescaler = SPI_BAUDRATEPRESCALER_32;
    HAL_SPI_Init(hspi);
}


/*----------------------------------------------------------------------
 * @brief: 	Set hspi1 clock to 18MHz
 * @param:
 * 			*hspi: Pointer to SPI handle Structure definition
 *
 ----------------------------------------------------------------------*/
void port_set_dw1000_fastrate(SPI_HandleTypeDef *hspi) {
	hspi->Init.BaudRatePrescaler = SPI_BAUDRATEPRESCALER_4;
    HAL_SPI_Init(hspi);
}
///*----------------------------------------------------------------------
// * @brief: 	Set hspi1 clock to 2.25MHz (UWB init)
// * @param: 	none
// *
// ----------------------------------------------------------------------*/
//void port_set_dw1000_slowrate(SPI_HandleTypeDef *hspi) {
//	hspi->Init.BaudRatePrescaler = SPI_BAUDRATEPRESCALER_16;
//    HAL_SPI_Init(hspi);
//}
//
//
///*----------------------------------------------------------------------
// * @brief: 	Set hspi1 clock to 18MHz
// * @param:
// * 			*hspi: Pointer to SPI handle Structure definition
// *
// ----------------------------------------------------------------------*/
//void port_set_dw1000_fastrate(SPI_HandleTypeDef *hspi) {
//	hspi->Init.BaudRatePrescaler = SPI_BAUDRATEPRESCALER_2;
//    HAL_SPI_Init(hspi);
//}

/*! -------------------------------------------------------------------
 * @brief:	Get the RX time-stamp in a 64-bit variable.
 * 			This function assumes that length of timestamps is 40 bits
 * @return  64-bit value of the read time-stamp.
 ----------------------------------------------------------------------*/
 uint64_t get_rx_timestamp_u64(void) {
    uint8_t ts_tab[5];
    uint64_t ts = 0;
    int i;
    dwt_readrxtimestamp(ts_tab);

    for (i = 4; i >= 0; i--) {
        ts <<= 8;
        ts |= ts_tab[i];
    }

//    // Debug
//    uint32_t ts_high = (uint32_t)(ts >> 32);
//    uint32_t ts_low = (uint32_t)(ts & 0xFFFFFFFF);
    return ts;
}


 /*! -------------------------------------------------------------------
  * @brief:  Get the current system time in a 64-bit variable.
  * @return  64-bit value of the current system time.
  ----------------------------------------------------------------------*/
 uint64_t get_sys_timestamp_u64(void) {
     uint8_t ts_tab[5];
     uint64_t ts = 0;
     dwt_readsystime(ts_tab);

     for (int i = 4; i >= 0; i--) {
         ts <<= 8;
         ts |= ts_tab[i];
     }
     return ts;
 }


 /*------------------------------------------------------------------------
  * @brief: 	Debug via huart1, use like printf (DMA)
  * @param:
  * 			*format: Pointer to format string
  -----------------------------------------------------------------------*/
 void debug_print(const char *format, ...) {
     if (!is_debug_tx_ready) {
         return;
     }

     // Ghép chuỗi
     va_list args;
     va_start(args, format);
     vsnprintf(debug_dma_buf, sizeof(debug_dma_buf), format, args);
     va_end(args);

     // Khóa cờ báo bận
     is_debug_tx_ready = false;

     // Giao việc cho DMA
     HAL_UART_Transmit_DMA(&huart1, (uint8_t*)debug_dma_buf, strlen(debug_dma_buf));
 }


 /*------------------------------------------------------------------------
  * @brief: 	Send data to central MCU (ESP32, etc...) (DMA)
  * @param:
  * 			*pData: Pointer to Data buffer
  * 			Size: Data length
  -----------------------------------------------------------------------*/
 void send_to_centralMCU(uint8_t *pData, uint16_t Size) {

     if (!is_central_tx_ready) {
         return;
     }

     // Chống tràn buffer
     if (Size > sizeof(central_dma_buf)) {
         Size = sizeof(central_dma_buf);
     }

     // Copy vào mảng toàn cục
     memcpy(central_dma_buf, pData, Size);

     // Khóa cờ báo bận
     is_central_tx_ready = false;

     // Giao việc cho DMA
     HAL_UART_Transmit_DMA(&huart2, central_dma_buf, Size);
 }


 /*------------------------------------------------------------------------
  * @brief: Tx Transfer completed callback
  * @param
  * 		*huart: UART handle.
  -----------------------------------------------------------------------*/
 void HAL_UART_TxCpltCallback(UART_HandleTypeDef *huart) {
	 // Kiểm tra xem ngắt này là của UART nào gửi xong
	 if (huart->Instance == USART1) {
		 // DMA 1 gửi xong log -> Mở khóa cho phép in log tiếp theo
		 is_debug_tx_ready = true;
	 }
	 else if (huart->Instance == USART2) {
		 // DMA 2 gửi xong bản tin cho ESP32 -> Mở khóa
		 is_central_tx_ready = true;
	 }
 }


#if (CURRENT_NODE_TYPE == TYPE_TAG)
 /* =====================================================================
  *				 	--- HÀM & LOGIC XỬ LÝ TAG ---
  * ====================================================================*/

 /* TDMA Timing (Microseconds tính từ lúc nhận Master Poll)
 * 	|----------------------------------30ms----------------------------------|
 *	|--2--|------------14--------------|--1--|-----------11------------|--2--|
 *	(MST_Poll)		(SLV_Poll)		   (BACKUP)		  (TAG_RES)       (DIST_CAL)
 */

 /*----------------------------------------------------------------------
  * @brief: [TAG] Finite State Machine
  ----------------------------------------------------------------------*/
 typedef enum {
	 TAG_STATE_ADV = 0,					//	Trạng thái Broadcast ADV
	 TAG_STATE_WAIT_MST_POLL,    		//  0-2ms		Lắng nghe Master Poll
	 TAG_STATE_WAIT_SLV_POLL,  			//  2-16ms: 	Lắng nghe Slave Poll
	 TAG_STATE_PREPARE_TAG_RES,  		//  16-28ms: 	Chuẩn bị gói Response
 } tag_fsm_state_t;


 /*----------------------------------------------------------------------
  * @brief: [TAG] Buffer, Variable & Flag
  ----------------------------------------------------------------------*/
// volatile bool is_synced_mst = false;

 volatile tag_fsm_state_t tag_state = TAG_STATE_ADV;	// Tag state (Defaut: STATE_ADV)
 volatile uint8_t my_tdma_index = 0;					// Tag TDMA slot
 volatile uint64_t master_poll_rx_ts = 0;				// Timestamp (DW1000) nhận Mst Poll

 volatile bool has_prepared_res = false;				// Cờ báo setup xong TX Response
 volatile bool recieved_mst_poll = false;				// Cờ báo nhận được Mst_beacon Poll
 static volatile bool flag_process_mst_poll = false;	// Cờ báo xử lý Mst Beacon Poll

// static bool is_synced = false;

 static uint32_t last_master_poll_ms = 0;				// Timestamp ms (STM32) lần gần nhất nhận Mst Poll
 static uint32_t last_adv_ms = 0;						// Timestamp ms (STM32) lần gần nhất gửi ADV

 // Frame buffer
 static pkt_tag_resp_t resp_payload;					// Payload Response
 static uwb_msg_frame_t resp_frame;						// Frame tổng Response
 static uwb_msg_frame_t adv_frame;						// Frame tổng ADV
 static pkt_master_poll_t cached_mst_poll;				// Buffer Mst Poll nhận
// static uint8_t rx_buffer[128];							// Buffer nhận

 // Slave Poll handle
 typedef struct {
     uint8_t slv_id;
     uint32_t rx_ts;
 } slv_poll_event_t;
 static volatile slv_poll_event_t slave_queue[TAG_EVENT_QUEUE_SIZE];
 static volatile uint8_t tag_ev_head = 0;
 static volatile uint8_t tag_ev_tail = 0;


 /*------------------------------------------------------------------------
  * @brief: [TAG] Push SLV Poll RX event to queue
  * @param
  * 		uint8_t slv_id: ID SLV Beacon
  * 		uint32_t rx_ts: RX timestamp
  -----------------------------------------------------------------------*/
 static void push_slv_poll_event(uint8_t slv_id, uint32_t rx_ts) {
     uint8_t next = (tag_ev_head + 1) % TAG_EVENT_QUEUE_SIZE;
     if (next != tag_ev_tail) {
    	 slave_queue[tag_ev_head].slv_id = slv_id;
    	 slave_queue[tag_ev_head].rx_ts = rx_ts;
         tag_ev_head = next;
     }
 }


 /*------------------------------------------------------------------------
  * @brief: [TAG] Pop SLV Poll RX event
  * @param
  * 		slv_poll_event_t* ev: Event queue
  -----------------------------------------------------------------------*/
 static bool pop_slv_poll_event(slv_poll_event_t* ev) {
     if (tag_ev_head == tag_ev_tail) return false;
     *ev = slave_queue[tag_ev_tail];
     tag_ev_tail = (tag_ev_tail + 1) % TAG_EVENT_QUEUE_SIZE;
     return true;
 }


 /*----------------------------------------------------------------------
  * @brief: [TAG] RX callback function
  * @param:
  * 		uwb_msg_frame_t *rx_frame: RX frame
  * 		uint8_t func_code: Msg function code
  ----------------------------------------------------------------------*/
 void tag_rx_handler(uwb_msg_frame_t *rx_frame, uint8_t func_code) {

	 // ===================== Master Beacon Poll =========================
	 if (func_code == FUNC_MASTER_POLL) {

		 __HAL_TIM_SET_COUNTER(&htim2, 0);

		 master_poll_rx_ts = get_rx_timestamp_u64();

		 memcpy(&cached_mst_poll, rx_frame->payload, sizeof(pkt_master_poll_t));
		 flag_process_mst_poll = true;
	 }

	 // ===================== Slave Beacon Poll ==========================
	 else if ((func_code == FUNC_SLAVE_POLL) && recieved_mst_poll) {

		 uint32_t rx_ts = dwt_readrxtimestamplo32();

		 pkt_slave_poll_t* spoll = (pkt_slave_poll_t*)rx_frame->payload;

		 push_slv_poll_event(spoll->slv_id, rx_ts);
	 }

	 dwt_rxenable(DWT_START_RX_IMMEDIATE);
 }


 /*------------------------------------------------------------------------
   * @brief: [TAG] Handle Advertising
   -----------------------------------------------------------------------*/
 static void handle_tag_state_adv (void) {

      // =================== MST POLL FLAG ======================
      if (flag_process_mst_poll) {
          flag_process_mst_poll = false;

          bool is_my_id_present = false;
          for (int i = 0; i < cached_mst_poll.tag_count; i++) {
              if (cached_mst_poll.tag_ids[i] == MY_TAG_ID) {
                  is_my_id_present = true;
                  my_tdma_index = i;
                  break;
              }
          }

          // Nếu Master đã thêm Tag vào danh sách mạng -> Lập tức tham gia Ranging!
          if (is_my_id_present) {
              last_master_poll_ms = HAL_GetTick();
              tag_state = TAG_STATE_WAIT_SLV_POLL; // Chuyển thẳng sang đợi Slave Poll
              resp_payload.beacon_count = 0;
              recieved_mst_poll = true;
              // Xóa queue cũ
              tag_ev_head = 0; tag_ev_tail = 0;

              return;
          }
      }

      // =========== THỰC HIỆN BROADCAST ADV ĐỊNH KỲ =============
      if (HAL_GetTick() - last_adv_ms > ADV_CYCLE_MS) {
          last_adv_ms = HAL_GetTick();

          // --- Chuẩn bị payload ADV --
          pkt_adv_t adv_payload;
          adv_payload.tag_id = MY_TAG_ID;
          adv_payload.func_code = FUNC_ADV;

          // --- Chuẩn bị ADV frame ---
          adv_frame.frame_ctrl = FRAME_CONTROL;
          adv_frame.pan_id = PAN_ID;
          adv_frame.dest_addr = BROADCAST_ID;
          adv_frame.src_addr = MY_TAG_ID;
          memcpy(adv_frame.payload, &adv_payload, sizeof(pkt_adv_t));

          uint16_t frame_len = MAC_HDR_LEN + sizeof(pkt_adv_t) + FCS_LEN;

          // --- Thực hiện Broadcast ADV ---
          dwt_write32bitreg(SYS_STATUS_ID, SYS_STATUS_TXFRS);
          dwt_writetxdata(frame_len, (uint8_t *)&adv_frame, 0);
          dwt_writetxfctrl(frame_len, 0, 1);
          int ret = dwt_starttx(DWT_START_TX_IMMEDIATE | DWT_RESPONSE_EXPECTED);

          // --- Kiểm tra & Debug ---
          if (ret == DWT_SUCCESS){
              while (!(dwt_read32bitreg(SYS_STATUS_ID) & SYS_STATUS_TXFRS))
              {};
              dwt_write32bitreg(SYS_STATUS_ID, SYS_STATUS_TXFRS);
              if (is_debug_tx_ready) debug_print("[TAG] Broadcast ADV -> OK!\r\n");
          } else {
              dwt_write32bitreg(SYS_STATUS_ID, SYS_STATUS_TXBERR);
              if (is_debug_tx_ready) debug_print("[TAG] Broadcast ADV -> FAIL!\r\n");
              dwt_rxreset();
              dwt_rxenable(DWT_START_RX_IMMEDIATE);
          }
      }
  }

 /*----------------------------------------------------------------------
  * @brief: [TAG] Handle TAG_STATE_WAIT_MST_POLL state
  * @param:
  * 		uint16_t elapsed_us: elapsed time (us)
  ----------------------------------------------------------------------*/
 static void handle_state_wait_mst_poll(uint16_t elapsed_us) {
     // Xử lý Master Poll bị đẩy vào Queue từ ISR
     if (flag_process_mst_poll) {
         flag_process_mst_poll = false;

         bool is_my_id_present = false;
         for (int i = 0; i < cached_mst_poll.tag_count; i++) {
             if (cached_mst_poll.tag_ids[i] == MY_TAG_ID) {
                 is_my_id_present = true;
                 my_tdma_index = i;
                 break;
             }
         }

         if (is_my_id_present) {
             last_master_poll_ms = HAL_GetTick();
             tag_state = TAG_STATE_WAIT_SLV_POLL;
             resp_payload.beacon_count = 0;
             recieved_mst_poll = true;

             // Xóa queue cũ
             tag_ev_head = 0;
             tag_ev_tail = 0;
         }
     }

     // =============== Timeout chuyển TAG_STATE_ADV ===============
     if (HAL_GetTick() - last_master_poll_ms > WAIT_MST_POLL_TIMEOUT_MS) {
         tag_state = TAG_STATE_ADV;
         recieved_mst_poll = false;
     }
 }

 /*----------------------------------------------------------------------
  * @brief: [TAG] Handle TAG_STATE_WAIT_SLV_POLL state
  * @param:
  * 		uint16_t elapsed_us: elapsed time (us)
  ----------------------------------------------------------------------*/
 static void handle_state_wait_slv_poll(uint16_t elapsed_us) {
	 slv_poll_event_t ev;

	 while (pop_slv_poll_event(&ev)){
		 int slot = resp_payload.beacon_count;

		 if (slot < MAX_SLAVES) {
			 resp_payload.rx_infos[slot].slv_beacon_id = ev.slv_id;
			 resp_payload.rx_infos[slot].poll_rx_ts = ev.rx_ts;
			 resp_payload.beacon_count++;
		 }
	 }

	 // =============== Timeout chuyển TAG_STATE_PREPARE_TAG_RES ===============
	 if (elapsed_us >= (MASTER_POLL_TIMEOUT + SLAVE_POLL_TIMEOUT - 1000)) {
		 has_prepared_res = false;
		 tag_state = TAG_STATE_PREPARE_TAG_RES;
		 dwt_forcetrxoff();

	 }
 }


 /*----------------------------------------------------------------------
  * @brief: [TAG] Handle TAG_STATE_PREPARE_TAG_RES state
  * @param:
  * 		uint16_t elapsed_us: elapsed time (us)
  ----------------------------------------------------------------------*/
 static void handle_state_prepare_tag_res(uint16_t elapsed_us) {

	 // =============== Chuẩn bị và Broadcast Tag Response ====================
	 if (!has_prepared_res) {

		 // Dùng mốc MST Poll
		 uint32_t delay_us = TAG_TDMA_BASE_US + 500 + (my_tdma_index * TAG_SLOT_TDMA_US);	// Tính toán TDMA time slot
		 uint64_t delay_dwt = (uint64_t)delay_us * UUS_TO_DWT_TIME;							// Quy đổi từ micro-giây sang DW1000 time units
		 uint64_t res_tx_ts_u64 = delay_dwt + master_poll_rx_ts;							// Timestamp Broadcast gói Response (DW1000)

		 res_tx_ts_u64 &= 0xFFFFFFFFFFULL;													// Lấy 40-bit thấp
		 uint32_t res_tx_ts_u32 = (uint32_t)(res_tx_ts_u64 >> 8);							// Masking lấy 32-bit (bỏ 8 bit thấp theo y/c Deca API)
		 dwt_setdelayedtrxtime(res_tx_ts_u32);												// Setup Delay TX


		 // --- Chuẩn bị Response payload ---
		 resp_payload.func_code = FUNC_TAG_RESP;
		 resp_payload.tag_id = MY_TAG_ID;
		 uint64_t actual_tx_time_u64 = (((uint64_t)(res_tx_ts_u32 & 0xFFFFFFFEUL)) << 8);	// Zeros 8-bit thấp
		 resp_payload.resp_tx_ts = (uint32_t)(actual_tx_time_u64 + TX_ANT_DLY);				// Bù Anten delay

		 // --- Chuẩn bị Response frame ---
		 resp_frame.frame_ctrl = FRAME_CONTROL;
		 resp_frame.pan_id = PAN_ID;
		 resp_frame.dest_addr = BROADCAST_ID;
		 uint16_t payload_len = (resp_payload.beacon_count * sizeof(rx_info_t)) + 7;	// Độ dài Payload
		 memcpy(resp_frame.payload, &resp_payload, payload_len);
		 uint16_t resp_frame_len = MAC_HDR_LEN + payload_len + FCS_LEN;					// Độ dài Response frame

		 // --- Nạp dữ liệu + Delay TX Response frame ---
		 dwt_writetxdata(resp_frame_len, (uint8_t*)&resp_frame, 0);
		 dwt_writetxfctrl(resp_frame_len, 0, 1);
		 int ret = dwt_starttx(DWT_START_TX_DELAYED);

		  // --- Kiểm tra & Debug ---
		  if (ret == DWT_SUCCESS){
			  while (!(dwt_read32bitreg(SYS_STATUS_ID) & SYS_STATUS_TXFRS))					// Đợi cờ truyền xong
			  {};
			  dwt_write32bitreg(SYS_STATUS_ID, SYS_STATUS_TXFRS);						// Xóa cờ TX: Transmit Frame Sent
		  } else {
			  dwt_write32bitreg(SYS_STATUS_ID, SYS_STATUS_TXBERR);						// Xóa cờ TX: Transmit Buffer Error
			  dwt_rxreset();															// Reset lại bộ receiver DW1000
			  dwt_rxenable(DWT_START_RX_IMMEDIATE);
		  }

		  has_prepared_res = true;														// Cờ setup xong TX Response
	 }

	 // ================== Chuyển trạng thái TAG_STATE_WAIT_MST_POLL ========================
	 if (elapsed_us >= ((CYCLE_PERIOD_MS * 1000) - 3000)) {
		 dwt_rxenable(DWT_START_RX_IMMEDIATE);
		 tag_state = TAG_STATE_WAIT_MST_POLL;
		 recieved_mst_poll = false;
		 memset(resp_payload.rx_infos, 0, sizeof(resp_payload.rx_infos));
//		 has_prepared_res = false;
	 }
 }


 /*----------------------------------------------------------------------
  * @brief: [TAG] Main loop
  ----------------------------------------------------------------------*/
 void tag_loop (void) {
	 uint16_t elapsed_us = __HAL_TIM_GET_COUNTER(&htim2);

	 switch (tag_state) {

	 	 case TAG_STATE_ADV:

	 		 /* ToDo: XỬ LÝ BẢN TIN VÀ ADV ĐỊNH KỲ -> DONE
	 		  * 	- Tạo payload + bọc MAC header
	 		  *		- TX Broadcast -> RX (Mỗi ADV_CYCLE_MS)
	 		  *		- Chuyển TAG_STATE_WAIT_SLV_POLL <=> Nhận FUNC_MASTER_POLL
	 		  *		- Handle RX callback
	 		  * */
	 		handle_tag_state_adv();

	 		break;

	 	 case TAG_STATE_WAIT_MST_POLL:

	 		 /* ToDo: LẮNG NGHE FUNC_MASTER_POLL -> DONE
	 		  * 	- Vừa vào TAG_STATE_WAIT_MST_POLL lưu lại start_time
	 		  * 	- Quay lại TAG_STATE_ADV <=> elasped = current_time - start_time >= 500ms
	 		  * 	- (Rx callback) Lưu lại rx_mst_poll_time (stm32) lần đầu làm mốc 0 (MST poll 3 lần). Dò ID bản thân
	 		  * 		+ Ko có bỏ qua (xóa rx_mst_poll_time)
	 		  * 		+ Nếu có lấy TDMA slot k (xóa start_time)
	 		  *		- Chuyển TAG_STATE_WAIT_SLV_POLL <=> current_time - rx_mst_poll_time > MASTER_POLL_TIMEOUT
	 		  * */
	 		 handle_state_wait_mst_poll(elapsed_us);
	 		 break;

	 	 case TAG_STATE_WAIT_SLV_POLL:

	 		 /* ToDo: LẮNG NGHE STATE_WAIT_SLV_POLL -> DONE
	 		  * 	- (Rx callback) Lưu lại ID Beacon và thời điểm nhận gói poll rx_slv_poll_time (dw1000)
	 		  *		- Chuyển TAG_STATE_PREPARE_TAG_RES <=> current_time - rx_mst_poll_time > MASTER_POLL_TIMEOUT + SLAVE_POLL_TIMEOUT
	 		  * */
	 		 handle_state_wait_slv_poll(elapsed_us);
	 		 break;

	 	 case TAG_STATE_PREPARE_TAG_RES:

	 		 /* ToDo: CHUẨN BỊ GÓI RES -> DONE
	 		  * 	- Đóng gói payload + bọc MAC header
	 		  * 		+ Response TX Timestamp (dw1000): tx_tag_response_time = dwt_readsystime() + delay
	 		  * 		+ Duyệt qua toàn bộ Slv_beacon Queue -> ghép Beacon ID với rx_slv_poll_time tương ứng
	 		  *		- Cài thời gian gửi sau delay = 500 + k * TAG_SLOT_TDMA_US
	 		  *		- Chuyển TAG_STATE_WAIT_MST_POLL khi gửi thành công
	 		  * */
	 		 handle_state_prepare_tag_res(elapsed_us);
	 		 break;
	 }
 }
#endif


#if (CURRENT_NODE_TYPE == TYPE_SLAVE)
 /* ====================================================================
  *			   --- HÀM & LOGIC XỬ LÝ SLV_BEACON ---
  * ===================================================================*/

 /* TDMA Timing (Microseconds tính từ lúc nhận Master Poll)
 * 	|----------------------------------30ms----------------------------------|
 *	|--2--|------------14--------------|--1--|-----------11------------|--2--|
 *	(MST_Poll)		(SLV_Poll)		   (BACKUP)		  (TAG_RES)       (DIST_CAL)
 */

 /*----------------------------------------------------------------------
  * @brief: [SLV_BEACON] Finite State Machine
  ----------------------------------------------------------------------*/
 typedef enum {
	 SLV_STATE_WAIT_MST_POLL,    		//  0-2ms		Lắng nghe Master Poll
	 SLV_STATE_PREPARE_SLV_POLL,  		//  2-16ms: 	Chuẩn bị gói Slv_Beacon Poll
	 SLV_STATE_WAIT_TAG_RES,  			//  16-28ms: 	Lắng nghe gói Response từ Tag
	 SLV_STATE_CALCULATE_DIST			//  28-30ms: 	Slv_Beacon tính toán k/c pha hiện tại
 } slv_fsm_state_t;


 /*----------------------------------------------------------------------
  * @brief: [SLV_BEACON] Variable & Flag
  ----------------------------------------------------------------------*/
 // State & Variable
 volatile slv_fsm_state_t slv_state = SLV_STATE_WAIT_MST_POLL;		// FSM state, Defaut SLV_STATE_WAIT_MST_POLL
 volatile uint8_t my_tdma_index = 0xFF;								// Slot TDMA, Defaut 0xFF -> Error
 volatile uint64_t master_poll_rx_ts = 0;							// Timestamp (DW1000) nhận MsT Poll

 // Flags
 volatile bool recieved_mst_poll = false;							// Cờ nhận Mst Poll
 static volatile bool flag_process_mst_poll = false;				// Cờ process dữ liệu Mst Poll
 static bool has_prepared_poll_tx = false;							// Cờ chuẩn bị gói Slv Poll
 static bool has_calculated = false;								// Cờ tính toán k/c mỗi pha Ranging

 // TX/RX Buffer
 static pkt_slave_poll_t slv_poll_payload;							// Buffer payload Slv Poll
 static uwb_msg_frame_t slv_poll_frame;								// Buffer frame Slv Poll
 static volatile pkt_master_poll_t cached_mst_poll;					// Buffer payload Mst Poll
 static uint8_t rx_buffer[128];

 // Rx ISR handle
 typedef struct {
     uint64_t rx_ts;
     int32_t carrier_integ;
     pkt_tag_resp_t payload;
 } tag_res_event_t;
 static volatile tag_res_event_t tag_queue[SLV_EVENT_QUEUE_SIZE];
 static volatile uint8_t slv_ev_head = 0;
 static volatile uint8_t slv_ev_tail = 0;

 // Tag handle
// static uint8_t active_tag_ids[MAX_TAGS];
 static uint8_t active_tag_count = 0;			// Số lượng Active tag chu kỳ hiện tại
 static uint8_t prev_active_tag_count = 0;		// Số lượng Active tag chu kỳ trước
 typedef struct {
	 uint8_t tag_id;							// ID Tag
     bool valid;								// Đã nhận được Response của Tag này chưa?
     int32_t carrier_integ;						// Carrier integer -> Dùng để tính clockoffset
     uint32_t poll_tx_ts_u32;       			// (DW1000) Mốc thời gian Slave TX Slave Poll
     uint32_t resp_rx_ts_u32;       			// (DW1000) Mốc thời gian Slave RX Tag Response
     uint32_t tag_poll_rx_ts;       			// (Từ Payload) Mốc Tag RX Slave Poll
     uint32_t tag_resp_tx_ts;       			// (Từ Payload) Mốc Tag TX Tag Response
 } slv_ranging_data_t;

 static slv_ranging_data_t ranging_data[MAX_TAGS];
 static double filtered_ratio[MAX_TAGS] = {0.0};


 /*----------------------------------------------------------------------
  * @brief: [SLV] Push RX Tag Response to event queue
  * @param:
  * 		pkt_tag_resp_t* payload: msg payload
  * 		uint64_t rx_ts: Tag Poll Rx timestamp
  * 		int32_t carrier: Carrier interger of that Tag
  ----------------------------------------------------------------------*/
 static void push_tag_res_event(pkt_tag_resp_t* payload, uint64_t rx_ts, int32_t carrier) {
     uint8_t next = (slv_ev_head + 1) % SLV_EVENT_QUEUE_SIZE;
     if (next != slv_ev_tail) {
    	 tag_queue[slv_ev_head].payload = *payload;
    	 tag_queue[slv_ev_head].rx_ts = rx_ts;
    	 tag_queue[slv_ev_head].carrier_integ = carrier;
         slv_ev_head = next;
     }
 }

 /*----------------------------------------------------------------------
  * @brief: [SLV] Pop Rx Tag Response out of event queue
  * @param:
  * 		tag_res_event_t* ev: Event queue
  ----------------------------------------------------------------------*/
 static bool pop_tag_res_event(tag_res_event_t* ev) {
     if (slv_ev_head == slv_ev_tail) return false;
     *ev = tag_queue[slv_ev_tail];
     slv_ev_tail = (slv_ev_tail + 1) % SLV_EVENT_QUEUE_SIZE;
     return true;
 }

 /*----------------------------------------------------------------------
  * @brief: [SLV] Setup & Initalisation
  ----------------------------------------------------------------------*/
 void slv_beacon_init(void) {
	 // Xác định TDMA slot
	 for (int i = 0; i < MAX_SLAVES; i++) {
		 if (MY_SLV_BEACON_ID == SLV_TOPOLOGY_LIST[i]) {
			 my_tdma_index = i;
			 break;
		 }
	 }

	 while (!is_debug_tx_ready) {}
	 debug_print("[SLV] Init: TDMA index = %d\r\n", my_tdma_index);

	 // --- Chuẩn bị header Slave Poll ---
	 slv_poll_frame.frame_ctrl = FRAME_CONTROL;
	 slv_poll_frame.pan_id = PAN_ID;
	 slv_poll_frame.dest_addr = BROADCAST_ID;
	 slv_poll_frame.src_addr = BROADCAST_ID;

	 slv_poll_payload.func_code = FUNC_SLAVE_POLL;
	 slv_poll_payload.slv_id = MY_SLV_BEACON_ID;

//	 for (int i = 0; i < MAX_TAGS; i++) {
//		 slv_poll_payload.distances[i].dist_cm = INVALID_DIST; 		// Chu kỳ chưa có kết quả đo mặc định lỗi
//	 }
	 prev_active_tag_count = 0;										// Chu kỳ đầu chưa có kết quả Ranging
	 dwt_rxenable(DWT_START_RX_IMMEDIATE);
 }


 /*----------------------------------------------------------------------
  * @brief: [SLV] Slave Beacon RX callback
  * @param:
  * 		uwb_msg_frame_t *rx_frame: Pointer to RX frame
  * 		uint8_t func_code: Msg function code
  ----------------------------------------------------------------------*/
 void slv_rx_handler(uwb_msg_frame_t *rx_frame, uint8_t func_code) {
	 // ====================== Master Beacon Poll ==========================
     if (func_code == FUNC_MASTER_POLL) {
    	 pkt_master_poll_t* mpoll_payload = (pkt_master_poll_t*)rx_frame->payload;

    	 // Check ID Master gửi
    	 if (mpoll_payload->mst_id == MY_MST_ID) {
             __HAL_TIM_SET_COUNTER(&htim2, 0);
             master_poll_rx_ts = get_rx_timestamp_u64();
             // Copy payload to buffer
             memcpy(&cached_mst_poll, mpoll_payload, sizeof(pkt_master_poll_t));
             flag_process_mst_poll = true;
             slv_state = SLV_STATE_WAIT_MST_POLL;

//             if (is_debug_tx_ready) debug_print("[SLV] Rcv MST\r\n");
    	 }
     }

     // ========================= Tag Response =============================
     else if ((func_code == FUNC_TAG_RESP) && recieved_mst_poll) {
         uint64_t rx_ts = get_rx_timestamp_u64();
         int32_t carrier = dwt_readcarrierintegrator();
         pkt_tag_resp_t* payload = (pkt_tag_resp_t*)rx_frame->payload;

         push_tag_res_event(payload, rx_ts, carrier);
     }

     dwt_rxenable(DWT_START_RX_IMMEDIATE);
 }


 /*----------------------------------------------------------------------
  * @brief: [SLV] Hanlde SLV_STATE_WAIT_MST_POLL
  ----------------------------------------------------------------------*/
 static void handle_slv_wait_mst_poll(void) {
	 if (flag_process_mst_poll) {

		 flag_process_mst_poll = false;
		 recieved_mst_poll = true;

		 active_tag_count = cached_mst_poll.tag_count;
		 if (active_tag_count > MAX_TAGS) {
			 active_tag_count = MAX_TAGS;
		 }

		 for (int i = 0; i < active_tag_count; i++){
			  ranging_data[i].tag_id = cached_mst_poll.tag_ids[i];
			  ranging_data[i].valid = false;
		 }

//		 // Debug
//		 if (is_debug_tx_ready) {
//			 debug_print("[SLV] Tag count: %d\r\n", active_tag_count);
//		 }

//		recieved_mst_poll = true;
		has_prepared_poll_tx = false;
		has_calculated = false;

		slv_ev_head = 0;
		slv_ev_tail = 0;

		slv_state = SLV_STATE_PREPARE_SLV_POLL;
		dwt_forcetrxoff();
	 }
 }



 /*----------------------------------------------------------------------
  * @brief: [SLV] Handle SLV_STATE_PREPARE_SLV_POLL state
  * @param:
  * 		uint16_t elapsed_us: Elasped time (us)
  ----------------------------------------------------------------------*/
 static void handle_slv_prepare_poll(uint16_t elapsed_us) {

	 // ===================== Chuẩn bị & TX Slave Beacon Poll ================================
	 if (recieved_mst_poll && !has_prepared_poll_tx && my_tdma_index != 0xFF) {

//		 dwt_forcetrxoff();
		 uint32_t my_slot_us = SLAVE_TDMA_BASE_US + (my_tdma_index * SLAVE_SLOT_TDMA_US);
		 uint32_t trigger_us = my_slot_us;

		 // Break khi chưa đến time slot
		 if (elapsed_us < trigger_us) {
			 return;
		 }

		 // Tính toán TDMA & Delay TX gói Slv Poll
//		 uint64_t sys_time = get_sys_timestamp_u64();
//		 uint64_t delay_dwt = (uint64_t)(1000 * UUS_TO_DWT_TIME);
//		 uint64_t poll_tx_time_u64 = (sys_time + delay_dwt) & 0xFFFFFFFFFFULL;		// Masking lấy 40-bit thấp
//		 uint32_t poll_tx_time_u32 = (uint32_t)(poll_tx_time_u64 >> 8);						// Lấy 32 bit cao
//		 dwt_setdelayedtrxtime(poll_tx_time_u32);

		 // Tính toán TDMA & Delay TX gói Slv Poll
//		 uint32_t delay_us = SLAVE_TDMA_BASE_US + (my_tdma_index * SLAVE_SLOT_TDMA_US);
//		 uint64_t delay_dwt = (uint64_t)delay_us * UUS_TO_DWT_TIME;
//		 uint64_t poll_tx_time_u64 = (master_poll_rx_ts + delay_dwt) & 0xFFFFFFFFFFULL;		// Masking lấy 40-bit thấp
//		 uint32_t poll_tx_time_u32 = (uint32_t)(poll_tx_time_u64 >> 8);						// Lấy 32 bit cao
//		 dwt_setdelayedtrxtime(poll_tx_time_u32);


		 // Chuẩn bị payload Slave Poll (Đính kèm payload chu kỳ trước)
		 slv_poll_payload.tag_count = prev_active_tag_count;
		 uint16_t payload_len = (prev_active_tag_count * sizeof(tag_dist_t)) + 3;
		 uint16_t frame_len = MAC_HDR_LEN + payload_len + FCS_LEN;
		 memcpy(slv_poll_frame.payload, &slv_poll_payload, payload_len);			// Payload Ranging pha trước

		 // --- Xóa sạch cờ trạng thái trước khi TX ---
		 dwt_write32bitreg(SYS_STATUS_ID, SYS_STATUS_TXFRS | SYS_STATUS_TXBERR);

		 // Nạp thanh ghi TX
		 dwt_writetxdata(frame_len, (uint8_t *)&slv_poll_frame, 0);
		 dwt_writetxfctrl(frame_len, 0, 1);

		 // Tx sau khoảng Delay, sau khi TX xong tự về IDLE
		 int ret = dwt_starttx(DWT_START_TX_IMMEDIATE);

		 if (ret != DWT_SUCCESS) {
			 dwt_write32bitreg(SYS_STATUS_ID, SYS_STATUS_TXBERR);					// Clear cờ
			 dwt_rxreset();
			 dwt_rxenable(DWT_START_RX_IMMEDIATE);
			  if (is_debug_tx_ready) debug_print("[SLV] Sending SLV Poll -> FAIL\r\n");
		 } else {
			 while (!(dwt_read32bitreg(SYS_STATUS_ID) & SYS_STATUS_TXFRS))			// Đợi cờ truyền xong
			 {};
			 dwt_write32bitreg(SYS_STATUS_ID, SYS_STATUS_TXFRS);					// Clear cờ

			 // Đọc & lưu timestamp gửi slv poll
			 uint32_t poll_tx_ts_u32 = dwt_readtxtimestamplo32();
			 for (int i = 0; i < active_tag_count; i++) {
				 ranging_data[i].poll_tx_ts_u32 = poll_tx_ts_u32;
			 }
		 }
		 // Khóa cờ Slv Poll
		 has_prepared_poll_tx = true;
	 }

	 // ==================== Timeout chuyển SLV_STATE_WAIT_TAG_RES ==============================
	 if (elapsed_us >= (MASTER_POLL_TIMEOUT + SLAVE_POLL_TIMEOUT - 1000)) {
		 dwt_rxenable(DWT_START_RX_IMMEDIATE);							// Bật lại RX
		 slv_state = SLV_STATE_WAIT_TAG_RES;
	 }
 }


 /*----------------------------------------------------------------------
  * @brief: [SLV] Handle SLV_STATE_WAIT_TAG_RES state
  * @param:
  * 		uint16_t elapsed_us: Elasped time (us)
  ----------------------------------------------------------------------*/
 static void handle_slv_wait_tag_res(uint16_t elapsed_us) {
	 tag_res_event_t ev;

	 // Bóc từng gói trong Ring buffer để xử lý
	 while (pop_tag_res_event(&ev)) {
		 // Duyệt tìm ID Tag trong danh sách active tag
		 for (int i = 0; i < active_tag_count; i++) {
			 if (ev.payload.tag_id == ranging_data[i].tag_id) {
				 // Duyệt tìm ID bản thân trong list beacon trong payload
				 for (int j = 0; j < ev.payload.beacon_count; j++) {
					 if (ev.payload.rx_infos[j].slv_beacon_id == MY_SLV_BEACON_ID) {
						 ranging_data[i].carrier_integ = ev.carrier_integ;
						 ranging_data[i].tag_poll_rx_ts = ev.payload.rx_infos[j].poll_rx_ts;
						 ranging_data[i].tag_resp_tx_ts = ev.payload.resp_tx_ts;
						 ranging_data[i].resp_rx_ts_u32 = (uint32_t)ev.rx_ts;
						 ranging_data[i].valid = true;
						 break;
					 }
				 }
				 break;
			 }
		 }
	 }

	 // ==================== Timeout chuyển SLV_STATE_CALCULATE_DIST ===========================
	 if (elapsed_us > (MASTER_POLL_TIMEOUT + SLAVE_POLL_TIMEOUT + TAG_RESPONSE_TIMEOUT)) {
		 dwt_forcetrxoff();									// Tắt RF
		 slv_state = SLV_STATE_CALCULATE_DIST;
//		 debug_print("[SLV] Current state -> CALCULATE_DIST\r\n");
	 }
 }



 /*----------------------------------------------------------------------
  * @brief:	Handle Filter & Calculate distance
  ----------------------------------------------------------------------*/
 static void handle_slv_calc_ranging(uint16_t elapsed_us) {
	 if (!has_calculated) {
		 // ================ Xử lý tính Khoảng cách (cm) với từng Tag ===============================
		 for (int i = 0; i < active_tag_count; i++) {
			 slv_poll_payload.distances[i].tag_id = ranging_data[i].tag_id;
			 if (ranging_data[i].valid) {

				 // Tính T_round
				 uint32_t t_round_u32 = ranging_data[i].resp_rx_ts_u32 - ranging_data[i].poll_tx_ts_u32;

				 // Tính T_reply
				 uint32_t t_reply_u32 = ranging_data[i].tag_resp_tx_ts - ranging_data[i].tag_poll_rx_ts;

				 // Tính Clock offset Ratio theo carrier_integ từng Tag
				 double clockOffsetRatio;
				 clockOffsetRatio = ranging_data[i].carrier_integ * (FREQ_OFFSET_MULTIPLIER * HERTZ_TO_PPM_MULTIPLIER_CHAN_2 / 1.0e6);

				 // Lọc
				 if (clockOffsetRatio > 0.000004) clockOffsetRatio = 0.000004;
				 if (clockOffsetRatio < -0.000004) clockOffsetRatio = -0.000004;
				 if (filtered_ratio[i] == 0.0) {
				     filtered_ratio[i] = clockOffsetRatio;
				 } else {
				     filtered_ratio[i] = 0.4 * clockOffsetRatio + 0.6 * filtered_ratio[i];
				 }

				 // Tính toán ToF và k/c (cm)
				 double tof = ((t_round_u32 - (double)t_reply_u32 * (1 - filtered_ratio[i])) / 2.0) * DWT_TIME_UNITS;
//				 double tof = ((t_round_u32 - (double)t_reply_u32 * (1.0f - clockOffsetRatio)) / 2.0) * DWT_TIME_UNITS;
				 double dist_cm = tof * SPEED_OF_LIGHT * 100;

				 // Lọc và điền payload
				 if (dist_cm > 0 && dist_cm < MAX_DIST_CM){
					 slv_poll_payload.distances[i].dist_cm = (uint16_t)(dist_cm);
				 } else {
					 slv_poll_payload.distances[i].dist_cm = INVALID_DIST;
				 }

			 } else {
				 slv_poll_payload.distances[i].dist_cm = INVALID_DIST;
			 }
		 }
		 // Chuẩn bị cho gửi piggy-backing ở gói Slave Poll chu kỳ sau
		 prev_active_tag_count = active_tag_count;
		 has_calculated = true;

//		 debug_print("%02X,%u\r\n",slv_poll_payload.distances[0].tag_id,slv_poll_payload.distances[0].dist_cm);

	 }

	 // =================== Timeout ============================
	 if (elapsed_us >= (((CYCLE_PERIOD_MS - 1) * 1000))) {
		 // Reset cờ
		 recieved_mst_poll = false;
		 has_calculated = false;

		 // Bật lại RX
//		 dwt_rxreset();
		 dwt_rxenable(DWT_START_RX_IMMEDIATE);
		 slv_state = SLV_STATE_WAIT_MST_POLL;
	 }
 }


 /*----------------------------------------------------------------------
  * @brief: [SLV_BEACON] Main loop
  ----------------------------------------------------------------------*/
 void slv_beacon_loop (void) {
	 uint16_t elapsed_us = __HAL_TIM_GET_COUNTER(&htim2);

	 switch (slv_state) {

	 	 case SLV_STATE_WAIT_MST_POLL:

	 		 /* ToDo: LẮNG NGHE MASTER POLL -> Done
	 		  * 	- (RX callback) Check xem đúng ID Mst_beacon quản lý không
	 		  * 		+) Lưu lại rx_mst_poll_time (stm32) lần đầu làm mốc 0
	 		  * */
	 		handle_slv_wait_mst_poll();
	 		break;

	 	 case SLV_STATE_PREPARE_SLV_POLL:

	 		 /* ToDo: CHUẨN BỊ GÓI SLAVE POLL -> Done
	 		  * 	- Đóng gói payload + bọc MAC header
	 		  * 		+ Duyệt qua Tag Queue, lấy dsach ID và k/c tính được pha Ranging trước
	 		  *		- Cài thời gian gửi sau delay = 500 + k * SLAVE_SLOT_TDMA_US
	 		  *		- Gửi xong -> xóa Tag queue và dữ liệu hiện tại
	 		  *		- Chuyển SLV_STATE_WAIT_TAG_RES khi thực hiện thành công
	 		  * */

	 		handle_slv_prepare_poll(elapsed_us);
	 		break;

	 	 case SLV_STATE_WAIT_TAG_RES:

	 		 /* ToDo: LẮNG NGHE TAG RESPONSE -> Done
	 		  * 	- (Rx callback) Nếu FUNC_TAG_RESP và dsach BeaconID có mình => Lưu lại ID TAG thông tin timestamp tương ứnggồm
	 		  * 		+ Thời điểm nhận gói Response của Tag đó: rx_tag_res_time (dw1000)
	 		  * 		+ Thời điểm TAG nhận gói Poll của Beacon (gói tin) : tag_rx_poll_time
	 		  *		- Chuyển SLV_STATE_CALCULATE_DIST <=>
	 		  *			current_time - rx_mst_poll_time > MASTER_POLL_TIMEOUT + SLAVE_POLL_TIMEOUT + TAG_RESPONSE_TIMEOUT
	 		  * */
	 		handle_slv_wait_tag_res(elapsed_us);
	 		break;

	 	 case SLV_STATE_CALCULATE_DIST:

	 		 /* ToDo: TÍNH TOÁN KHOẢNG CÁCH VỚI CÁC TAG -> Done
	 		  * 	- Xóa rx_mst_poll_time (stm32)
	 		  * 	- Tính toán k/c với từng Tag => Lưu struct
	 		  * 	- Chuyển SLV_STATE_WAIT_MST_POLL khi tính tính toán xong
	 		  * */

	 		handle_slv_calc_ranging(elapsed_us);
	 		break;
	 }
 }

#endif


#if (CURRENT_NODE_TYPE == TYPE_MASTER)
 /* =====================================================================
  *			   --- HÀM & LOGIC XỬ LÝ MST_BEACON ---
  * ===================================================================*/

 /* TDMA Timing (Microseconds tính từ lúc nhận Master Poll)
 * 	|----------------------------------30ms----------------------------------|
 *	|--2--|------------14--------------|--1--|-----------11------------|--2--|
 *	(MST_Poll)		(SLV_Poll)		   (BACKUP)		  (TAG_RES)       (DIST_CAL)
 */

 /*----------------------------------------------------------------------
  * @brief: [MST_BEACON] Finite State Machine
  ----------------------------------------------------------------------*/
 typedef enum {
	 MST_STATE_PREPARE_MST_POLL,
	 MST_STATE_LISTENING_PACKET,
 } mst_fsm_state_t;
//
 /*----------------------------------------------------------------------
  * @brief: [MST_BEACON] Variable & Flag
  ----------------------------------------------------------------------*/
 mst_fsm_state_t mst_state = MST_STATE_PREPARE_MST_POLL;

 // --- Flags ---
 static bool rf_is_idle = false;
 uint32_t end_of_rf_activity = TAG_TDMA_BASE_US + (MAX_TAGS * TAG_SLOT_TDMA_US) + 1000;

 // --- Tag Queue ---
 typedef struct {
     uint8_t tag_id;
     uint8_t ttl;
 } mst_active_tag_t;

 static mst_active_tag_t tag_queue[MAX_TAGS];
 static uint8_t tag_queue_count = 0;

 // --- Slave Poll Queue (Ring Buffer) ---
 typedef struct {
     bool has_data;
     pkt_slave_poll_t payload;
 } slv_poll_msg_t;

 static slv_poll_msg_t slv_msg_queue[MSG_QUEUE_SIZE];
 static volatile uint8_t msg_head = 0; 						// Head
 static volatile uint8_t msg_tail = 0; 						// Tail

 // --- Buffer ---
 pkt_master_poll_t mst_poll_payload;
 uwb_msg_frame_t mst_poll_frame;


 /*----------------------------------------------------------------------
  * @brief: [MST] Handle function
  ----------------------------------------------------------------------*/
 // Hàm đẩy data vào Ring Buffer
 static void push_slv_msg(pkt_slave_poll_t* spoll) {
     uint8_t next = (msg_head + 1) % MSG_QUEUE_SIZE;
     if (next != msg_tail) { // Tránh tràn Queue
         slv_msg_queue[msg_head].payload = *spoll;
         slv_msg_queue[msg_head].has_data = true;
         msg_head = next;
     }
 }

 // Hàm lấy data từ Ring Buffer (Main Loop)
 static bool pop_slv_msg(pkt_slave_poll_t* spoll) {
     if (msg_head == msg_tail) return false; // Queue rỗng

     *spoll = slv_msg_queue[msg_tail].payload;
     slv_msg_queue[msg_tail].has_data = false;
     msg_tail = (msg_tail + 1) % MSG_QUEUE_SIZE;
     return true;
 }


 /*----------------------------------------------------------------------
  * @brief: [MST] Setup & Initialise
  ----------------------------------------------------------------------*/
 void mst_beacon_init(void) {
     tag_queue_count = 0;
     msg_head = 0;
     msg_tail = 0;
     mst_state = MST_STATE_PREPARE_MST_POLL;
//     debug_print("[MST] Current state -> PREPARE_MST_POLL\r\n");
 }


 /*----------------------------------------------------------------------
  * @brief: Xử lý Ngắt Nhận DW1000 RX Callback cho Master
  ----------------------------------------------------------------------*/
 void mst_rx_handler(uwb_msg_frame_t *rx_frame, uint8_t func_code) {

     // ========================== Slave Poll ============================
     if (func_code == FUNC_SLAVE_POLL) {
         pkt_slave_poll_t* slv_poll_payload = (pkt_slave_poll_t*)rx_frame->payload;

         // Check is_my_slave
         bool is_my_slave = false;
         for (int i = 0; i < MAX_SLAVES; i++) {
             if (CONTROL_SLV_LIST[i] == slv_poll_payload->slv_id) {
                 is_my_slave = true;
                 break;
             }
         }

         // Push payload vào Ring buffer, xử lý ở FSM sau
         if (is_my_slave) {
             push_slv_msg(slv_poll_payload);
         }

//         dwt_rxenable(DWT_START_RX_IMMEDIATE);
     }
     // =================== Tag Response & Tag ADV =======================
     else if (func_code == FUNC_TAG_RESP || func_code == FUNC_ADV) {
         uint8_t tid;
         if (func_code == FUNC_ADV) {
             tid = ((pkt_adv_t*)rx_frame->payload)->tag_id;
         } else {
             tid = ((pkt_tag_resp_t*)rx_frame->payload)->tag_id;
         }

         // Tìm và gia hạn TTL cho Tag
         bool found = false;
         for (int i = 0; i < tag_queue_count; i++) {
             if (tag_queue[i].tag_id == tid) {
                 tag_queue[i].ttl = TAG_TTL_MAX;
                 found = true;
                 break;
             }
         }

         // Tag mới -> Thêm vào
         if (!found && tag_queue_count < MAX_TAGS) {
             tag_queue[tag_queue_count].tag_id = tid;
             tag_queue[tag_queue_count].ttl = TAG_TTL_MAX;
             tag_queue_count++;
         }

//         dwt_rxenable(DWT_START_RX_IMMEDIATE);
     }
     dwt_rxenable(DWT_START_RX_IMMEDIATE);
 }


 /*----------------------------------------------------------------------
  * @brief: Hàm xử lý trạng thái MST_STATE_PREPARE_MST_POLL
  ----------------------------------------------------------------------*/
 static void handle_mst_prepare_poll (uint16_t elapsed_us) {

	 // ============= Chốt danh sách & cập nhật trạng thái Active Tag ================
	 /* Khóa ngắt RX khi chốt danh sách do nếu trong lúc đang cbi Mst Poll có Tag mới ADV
	  * -> tag_queue_count bị thay đổi, dẫn tới sai gói tin TX
	  * */
	 __disable_irq();											// Khóa Ngắt

	 // Xóa Tag có TTL == 0 khởi danh sách Active Tag
	 for (int i = 0; i < tag_queue_count; i++) {
		 tag_queue[i].ttl--;

		 // Mất kết nối quá TAG_TTL_MAX
		 if (tag_queue[i].ttl == 0) {
			 for (int j = i; j < tag_queue_count - 1; j++) {
				 tag_queue[j] = tag_queue[j + 1];				// Dồn Queue
			 }
			 tag_queue_count--;									// Giảm queue_count
			 i--;												// Xét lại vị trí i do bị dồn
		 }
	 }
	 // ====================== Chuẩn bị Master Poll =============================
	 mst_poll_frame.frame_ctrl = FRAME_CONTROL;
	 mst_poll_frame.pan_id = PAN_ID;
	 mst_poll_frame.dest_addr = BROADCAST_ID;

	 mst_poll_payload.func_code = FUNC_MASTER_POLL;
	 mst_poll_payload.mst_id = MY_MST_BEACON_ID;
	 mst_poll_payload.tag_count = tag_queue_count;

	 for (int i = 0; i < tag_queue_count; i++) {
		 mst_poll_payload.tag_ids[i] = tag_queue[i].tag_id;
	 }

	 __enable_irq();											// Mở lại ngắt

	 // Tính toán độ dài bản tin + nạp payload
	 uint16_t payload_len = 3 + tag_queue_count * sizeof(mst_poll_payload.tag_ids[0]);
	 uint16_t frame_len = MAC_HDR_LEN + payload_len + FCS_LEN;
	 memcpy(mst_poll_frame.payload, &mst_poll_payload, payload_len);

	 dwt_forcetrxoff();

	 // Nạp dữ liệu TX
	 dwt_writetxdata(frame_len, (uint8_t*)&mst_poll_frame, 0);
	 dwt_writetxfctrl(frame_len, 0, 1);

	 // Gửi và tự động bật RX
	 int ret = dwt_starttx(DWT_START_TX_IMMEDIATE | DWT_RESPONSE_EXPECTED);

	 // Reset TIM2 làm mốc 0 hệ thống
	 __HAL_TIM_SET_COUNTER(&htim2, 0);


	 // Debug
	  if (ret == DWT_SUCCESS){
		  while (!(dwt_read32bitreg(SYS_STATUS_ID) & SYS_STATUS_TXFRS))		// Chờ cờ TX xong
		  {};
		  dwt_write32bitreg(SYS_STATUS_ID, SYS_STATUS_TXFRS);				// Xóa cờ TX: Transmit Frame Sent
		  mst_state = MST_STATE_LISTENING_PACKET;
//		  debug_print("[MST] Broadcast MST Poll -> OK\r\n");
	  } else {
		  dwt_write32bitreg(SYS_STATUS_ID, SYS_STATUS_TXBERR);				// Xóa cờ TX: Transmit Buffer Error
//		  debug_print("[MST] Broadcast MST Poll -> FAIL\r\n");
		  dwt_rxreset();													// Reset lại bộ receiver DW1000
		  dwt_rxenable(DWT_START_RX_IMMEDIATE);
		  mst_state = MST_STATE_LISTENING_PACKET;

	  }
 }


 /*----------------------------------------------------------------------
  * @brief: Hàm xử lý trạng thái MST_STATE_LISTENING_PACKET
  ----------------------------------------------------------------------*/
 static void handle_mst_listening_packet (uint16_t elapsed_us) {
	 // ============== Xử lý dữ liệu Ranging từng Slv Beacon trong Queue ==========
	 pkt_slave_poll_t slv_poll_payload;

	 // Check xem UART2 DMA có rảnh không
	 if (is_central_tx_ready) {
		 if (pop_slv_msg(&slv_poll_payload)) {

			 char uart_buf[128];
			 int len = sprintf(uart_buf, "0x%02X", slv_poll_payload.slv_id);
			 int tag_count = slv_poll_payload.tag_count;
			 if (tag_count > MAX_TAGS) {
				 tag_count = MAX_TAGS;
			 }

			 // Duyệt qua payload để lấy dsach Tag ID cùng distance đo được
			 for (int i = 0; i < tag_count; i++) {
				 uint16_t dist_cm = slv_poll_payload.distances[i].dist_cm;
				 if (dist_cm != INVALID_DIST){
					 uint8_t tag_id = slv_poll_payload.distances[i].tag_id;
					 len += sprintf(uart_buf + len, ",0x%02X,%u", tag_id, dist_cm);
				 }
			 }

			 // Chốt chuỗi
			 len += sprintf(uart_buf + len, "\r\n");

			 // |BeaconID,TagID_1,Dist_1,TagID_2,Dist_2,...|
			 send_to_centralMCU((uint8_t*)uart_buf, len);
//			 debug_print(uart_buf);
		 }
	 }

	 // ================== Chuyển DW1000 về IDLE đợi chu kỳ sau =====================
	 if ((elapsed_us > end_of_rf_activity) && !rf_is_idle) {
		 dwt_forcetrxoff();
		 rf_is_idle = true;
	 }

	// ================== Timeout =====================
	if (elapsed_us >= (CYCLE_PERIOD_MS + 1) * 1000) {
		rf_is_idle = false;
		dwt_rxreset();
		mst_state = MST_STATE_PREPARE_MST_POLL;
	}
 }


 /*----------------------------------------------------------------------
  * @brief: [MST] Main loop
  ----------------------------------------------------------------------*/
 void mst_beacon_loop (void) {
	 uint16_t elapsed_us = __HAL_TIM_GET_COUNTER(&htim2);

	 switch (mst_state){

	 	 case MST_STATE_PREPARE_MST_POLL:

	 		 /* ToDo: XỬ LÝ BROADCAST MST_POLL -> Done
	 		  * 	- Lấy timestamp đầu chu kỳ mới (stm32): start_time
	 		  * 	- Tạo gói Master Poll (Danh sách Tag từ Queue)
	 		  *		- Xóa Tag Queue và Ranging data pha trước
	 		  *		- Chuyển MST_STATE_LISTENING_PACKET <=> current_time - start_time > MASTER_POLL_TIMEOUT
	 		  * */
	 		handle_mst_prepare_poll(elapsed_us);
	 		break;

	 	 case MST_STATE_LISTENING_PACKET:

	 		 /* ToDo: XỬ LÝ NHẬN SLV_POLL + TAG_RES + TAG ADV (CALLBACK) -> Done
	 		  * 	- Nếu SLV_POLL	-> Đọc Dist và ID của từng Tag trong gói, lưu struct và forward qua UART
	 		  * 		|BeaconID,TagID_1,Dist_1,TagID_2,Dist_2,...|
	 		  *		- Nếu TAG_RES	-> Lưu ID Tag vào Queue để MST_POLL pha sau
	 		  *		- Nếu ADV		-> Lưu ID Tag vào Queue để MST_POLL pha sau
	 		  *		- Chuyển MST_STATE_PREPARE_MST_POLL <=>
	 		  *			current_time - start_time > MASTER_POLL_TIMEOUT + SLAVE_POLL_TIMEOUT
	 		  *											+ TAG_RESPONSE_TIMEOUT + DIST_CAL_TIMEOUT
	 		  * */
	 		handle_mst_listening_packet(elapsed_us);
	 		break;
	 }
 }

#endif
