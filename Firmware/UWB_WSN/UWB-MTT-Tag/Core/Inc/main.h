/* USER CODE BEGIN Header */
/**
  ******************************************************************************
  * @file           : main.h
  * @brief          : Header for main.c file.
  *                   This file contains the common defines of the application.
  ******************************************************************************
  * @attention
  *
  * Copyright (c) 2026 STMicroelectronics.
  * All rights reserved.
  *
  * This software is licensed under terms that can be found in the LICENSE file
  * in the root directory of this software component.
  * If no LICENSE file comes with this software, it is provided AS-IS.
  *
  ******************************************************************************
  */
/* USER CODE END Header */

/* Define to prevent recursive inclusion -------------------------------------*/
#ifndef __MAIN_H
#define __MAIN_H

#ifdef __cplusplus
extern "C" {
#endif

/* Includes ------------------------------------------------------------------*/
#include "stm32f1xx_hal.h"

/* Private includes ----------------------------------------------------------*/
/* USER CODE BEGIN Includes */

#include "deca_device_api.h"
#include "deca_param_types.h"
#include "deca_regs.h"
#include "deca_version.h"
#include "uwb_shared_def.h"

#include <stdint.h>
#include <stdbool.h>
#include <string.h>

/* USER CODE END Includes */

/* Exported types ------------------------------------------------------------*/
/* USER CODE BEGIN ET */

/* USER CODE END ET */

/* Exported constants --------------------------------------------------------*/
/* USER CODE BEGIN EC */

/* USER CODE END EC */

/* Exported macro ------------------------------------------------------------*/
/* USER CODE BEGIN EM */

/* USER CODE END EM */

/* Exported functions prototypes ---------------------------------------------*/
void Error_Handler(void);

/* USER CODE BEGIN EFP */

/* USER CODE END EFP */

/* Private defines -----------------------------------------------------------*/
#define LED_1_Pin GPIO_PIN_13
#define LED_1_GPIO_Port GPIOC
#define LED_2_Pin GPIO_PIN_14
#define LED_2_GPIO_Port GPIOC
#define LED_3_Pin GPIO_PIN_15
#define LED_3_GPIO_Port GPIOC
#define DW_NSS_Pin GPIO_PIN_4
#define DW_NSS_GPIO_Port GPIOA
#define DW_RESET_Pin GPIO_PIN_0
#define DW_RESET_GPIO_Port GPIOB
#define DW_IRQ_Pin GPIO_PIN_1
#define DW_IRQ_GPIO_Port GPIOB
#define DW_IRQ_EXTI_IRQn EXTI1_IRQn

/* USER CODE BEGIN Private defines */

/* USER CODE END Private defines */

#ifdef __cplusplus
}
#endif

#endif /* __MAIN_H */
