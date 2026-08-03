################################################################################
# Automatically-generated file. Do not edit!
# Toolchain: GNU Tools for STM32 (13.3.rel1)
################################################################################

-include ../makefile.init

RM := rm -rf

# All of the sources participating in the build are defined here
-include sources.mk
-include UWB_middleware/platform/subdir.mk
-include UWB_middleware/decadriver/subdir.mk
-include Drivers/STM32F1xx_HAL_Driver/Src/subdir.mk
-include Core/Startup/subdir.mk
-include Core/Src/subdir.mk
-include objects.mk

ifneq ($(MAKECMDGOALS),clean)
ifneq ($(strip $(S_DEPS)),)
-include $(S_DEPS)
endif
ifneq ($(strip $(S_UPPER_DEPS)),)
-include $(S_UPPER_DEPS)
endif
ifneq ($(strip $(C_DEPS)),)
-include $(C_DEPS)
endif
endif

-include ../makefile.defs

OPTIONAL_TOOL_DEPS := \
$(wildcard ../makefile.defs) \
$(wildcard ../makefile.init) \
$(wildcard ../makefile.targets) \


BUILD_ARTIFACT_NAME := UWB-MTT-Mst_Beacon
BUILD_ARTIFACT_EXTENSION := elf
BUILD_ARTIFACT_PREFIX :=
BUILD_ARTIFACT := $(BUILD_ARTIFACT_PREFIX)$(BUILD_ARTIFACT_NAME)$(if $(BUILD_ARTIFACT_EXTENSION),.$(BUILD_ARTIFACT_EXTENSION),)

# Add inputs and outputs from these tool invocations to the build variables 
EXECUTABLES += \
UWB-MTT-Mst_Beacon.elf \

MAP_FILES += \
UWB-MTT-Mst_Beacon.map \

SIZE_OUTPUT += \
default.size.stdout \

OBJDUMP_LIST += \
UWB-MTT-Mst_Beacon.list \


# All Target
all: main-build

# Main-build Target
main-build: UWB-MTT-Mst_Beacon.elf secondary-outputs

# Tool invocations
UWB-MTT-Mst_Beacon.elf UWB-MTT-Mst_Beacon.map: $(OBJS) $(USER_OBJS) F:\Workplace\IPS_Firefighting_training_system\Firmware_src_20252\[STM32]-UWB_Ranging\UWB-MTT-Mst_Beacon\STM32F103C8TX_FLASH.ld makefile objects.list $(OPTIONAL_TOOL_DEPS)
	arm-none-eabi-gcc -o "UWB-MTT-Mst_Beacon.elf" @"objects.list" $(USER_OBJS) $(LIBS) -mcpu=cortex-m3 -T"F:\Workplace\IPS_Firefighting_training_system\Firmware_src_20252\[STM32]-UWB_Ranging\UWB-MTT-Mst_Beacon\STM32F103C8TX_FLASH.ld" --specs=nosys.specs -Wl,-Map="UWB-MTT-Mst_Beacon.map" -Wl,--gc-sections -static --specs=nano.specs -mfloat-abi=soft -mthumb -Wl,--start-group -lc -lm -Wl,--end-group
	@echo 'Finished building target: $@'
	@echo ' '

default.size.stdout: $(EXECUTABLES) makefile objects.list $(OPTIONAL_TOOL_DEPS)
	arm-none-eabi-size  $(EXECUTABLES)
	@echo 'Finished building: $@'
	@echo ' '

UWB-MTT-Mst_Beacon.list: $(EXECUTABLES) makefile objects.list $(OPTIONAL_TOOL_DEPS)
	arm-none-eabi-objdump -h -S $(EXECUTABLES) > "UWB-MTT-Mst_Beacon.list"
	@echo 'Finished building: $@'
	@echo ' '

# Other Targets
clean:
	-$(RM) UWB-MTT-Mst_Beacon.elf UWB-MTT-Mst_Beacon.list UWB-MTT-Mst_Beacon.map default.size.stdout
	-@echo ' '

secondary-outputs: $(SIZE_OUTPUT) $(OBJDUMP_LIST)

fail-specified-linker-script-missing:
	@echo 'Error: Cannot find the specified linker script. Check the linker settings in the build configuration.'
	@exit 2

warn-no-linker-script-specified:
	@echo 'Warning: No linker script specified. Check the linker settings in the build configuration.'

.PHONY: all clean dependents main-build fail-specified-linker-script-missing warn-no-linker-script-specified

-include ../makefile.targets
