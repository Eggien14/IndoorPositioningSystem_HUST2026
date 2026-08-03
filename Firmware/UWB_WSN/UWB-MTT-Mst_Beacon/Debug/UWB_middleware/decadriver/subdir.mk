################################################################################
# Automatically-generated file. Do not edit!
# Toolchain: GNU Tools for STM32 (13.3.rel1)
################################################################################

# Add inputs and outputs from these tool invocations to the build variables 
C_SRCS += \
../UWB_middleware/decadriver/deca_device.c \
../UWB_middleware/decadriver/deca_params_init.c 

OBJS += \
./UWB_middleware/decadriver/deca_device.o \
./UWB_middleware/decadriver/deca_params_init.o 

C_DEPS += \
./UWB_middleware/decadriver/deca_device.d \
./UWB_middleware/decadriver/deca_params_init.d 


# Each subdirectory must supply rules for building sources it contributes
UWB_middleware/decadriver/%.o UWB_middleware/decadriver/%.su UWB_middleware/decadriver/%.cyclo: ../UWB_middleware/decadriver/%.c UWB_middleware/decadriver/subdir.mk
	arm-none-eabi-gcc "$<" -mcpu=cortex-m3 -std=gnu11 -g3 -DDEBUG -DUSE_HAL_DRIVER -DSTM32F103xB -c -I../Core/Inc -I../Drivers/STM32F1xx_HAL_Driver/Inc -I../Drivers/STM32F1xx_HAL_Driver/Inc/Legacy -I../Drivers/CMSIS/Device/ST/STM32F1xx/Include -I../Drivers/CMSIS/Include -I"F:/Workplace/IPS_Firefighting_training_system/Firmware_src_20252/[STM32]-UWB_Ranging/UWB-MTT-Mst_Beacon/UWB_middleware/decadriver" -I"F:/Workplace/IPS_Firefighting_training_system/Firmware_src_20252/[STM32]-UWB_Ranging/UWB-MTT-Mst_Beacon/UWB_middleware/platform" -O0 -ffunction-sections -fdata-sections -Wall -fstack-usage -fcyclomatic-complexity -MMD -MP -MF"$(@:%.o=%.d)" -MT"$@" --specs=nano.specs -mfloat-abi=soft -mthumb -o "$@"

clean: clean-UWB_middleware-2f-decadriver

clean-UWB_middleware-2f-decadriver:
	-$(RM) ./UWB_middleware/decadriver/deca_device.cyclo ./UWB_middleware/decadriver/deca_device.d ./UWB_middleware/decadriver/deca_device.o ./UWB_middleware/decadriver/deca_device.su ./UWB_middleware/decadriver/deca_params_init.cyclo ./UWB_middleware/decadriver/deca_params_init.d ./UWB_middleware/decadriver/deca_params_init.o ./UWB_middleware/decadriver/deca_params_init.su

.PHONY: clean-UWB_middleware-2f-decadriver

