################################################################################
# Automatically-generated file. Do not edit!
# Toolchain: GNU Tools for STM32 (13.3.rel1)
################################################################################

# Add inputs and outputs from these tool invocations to the build variables 
C_SRCS += \
../UWB_middleware/platform/deca_mutex.c \
../UWB_middleware/platform/deca_range_tables.c \
../UWB_middleware/platform/deca_sleep.c \
../UWB_middleware/platform/deca_spi.c 

OBJS += \
./UWB_middleware/platform/deca_mutex.o \
./UWB_middleware/platform/deca_range_tables.o \
./UWB_middleware/platform/deca_sleep.o \
./UWB_middleware/platform/deca_spi.o 

C_DEPS += \
./UWB_middleware/platform/deca_mutex.d \
./UWB_middleware/platform/deca_range_tables.d \
./UWB_middleware/platform/deca_sleep.d \
./UWB_middleware/platform/deca_spi.d 


# Each subdirectory must supply rules for building sources it contributes
UWB_middleware/platform/%.o UWB_middleware/platform/%.su UWB_middleware/platform/%.cyclo: ../UWB_middleware/platform/%.c UWB_middleware/platform/subdir.mk
	arm-none-eabi-gcc "$<" -mcpu=cortex-m3 -std=gnu11 -g3 -DDEBUG -DUSE_HAL_DRIVER -DSTM32F103xB -c -I../Core/Inc -I../Drivers/STM32F1xx_HAL_Driver/Inc -I../Drivers/STM32F1xx_HAL_Driver/Inc/Legacy -I../Drivers/CMSIS/Device/ST/STM32F1xx/Include -I../Drivers/CMSIS/Include -I"F:/Workplace/IPS_Firefighting_training_system/Firmware_src_20252/[STM32]-UWB_Ranging/UWB-MTT-Mst_Beacon/UWB_middleware/decadriver" -I"F:/Workplace/IPS_Firefighting_training_system/Firmware_src_20252/[STM32]-UWB_Ranging/UWB-MTT-Mst_Beacon/UWB_middleware/platform" -O0 -ffunction-sections -fdata-sections -Wall -fstack-usage -fcyclomatic-complexity -MMD -MP -MF"$(@:%.o=%.d)" -MT"$@" --specs=nano.specs -mfloat-abi=soft -mthumb -o "$@"

clean: clean-UWB_middleware-2f-platform

clean-UWB_middleware-2f-platform:
	-$(RM) ./UWB_middleware/platform/deca_mutex.cyclo ./UWB_middleware/platform/deca_mutex.d ./UWB_middleware/platform/deca_mutex.o ./UWB_middleware/platform/deca_mutex.su ./UWB_middleware/platform/deca_range_tables.cyclo ./UWB_middleware/platform/deca_range_tables.d ./UWB_middleware/platform/deca_range_tables.o ./UWB_middleware/platform/deca_range_tables.su ./UWB_middleware/platform/deca_sleep.cyclo ./UWB_middleware/platform/deca_sleep.d ./UWB_middleware/platform/deca_sleep.o ./UWB_middleware/platform/deca_sleep.su ./UWB_middleware/platform/deca_spi.cyclo ./UWB_middleware/platform/deca_spi.d ./UWB_middleware/platform/deca_spi.o ./UWB_middleware/platform/deca_spi.su

.PHONY: clean-UWB_middleware-2f-platform

