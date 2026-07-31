#include "services/read_imu.h"

/*#############################################################################################################*/
/**
 * @brief Initialize the IMU sensor
 * @return None
 */
void init_IMU(void)
{
// Init I2C
Wire.begin(I2C_SDA, I2C_SCL);

// // Configure sensor 1
// Wire.beginTransmission(BNO055_EX_ADDRESS);
// Wire.write(BNO055_OPR_MODE_ADDR);
// Wire.write(BNO055_MODE_NDOF);
// Wire.endTransmission();

// delay(BNO055_CONFIG_DELAY);

// Configure sensor 2
Wire.beginTransmission(BNO055_IN_ADDRESS);
Wire.write(BNO055_OPR_MODE_ADDR);
Wire.write(BNO055_MODE_NDOF);
Wire.endTransmission();

delay(BNO055_CONFIG_DELAY);
}

/*#############################################################################################################*/
/**
 * @brief Read raw sensor data from BNO055 and store in IMU_Raw_Data structure
 * @param imu_raw_data Pointer to structure where raw sensor data will be stored
 * @param device_address I2C address of the BNO055 sensor
 *
 * This function reads all sensor data in sequence:
 * - Accelerometer (X,Y,Z) starting from ACC_DATA_START
 * - Gyroscope (X,Y,Z) starting from GYRO_DATA_START
 * - Magnetometer (X,Y,Z) starting from MAG_DATA_START
 * - Euler angles (X,Y,Z) starting from EULER_DATA_START
 * - Quaternion (W,X,Y,Z) starting from QUATERNION_DATA_START
 */

/*#############################################################################################################*/

void read_IMU_raw_data(IMU_Raw_Data *imu_raw_data, uint8_t device_address)
{
    // Read Accelerometer data (X,Y,Z)
    // Each axis requires 2 registers (LSB + MSB)
    imu_raw_data->acc_raw.x = read_16_bit_LSB_MSB(ACC_DATA_START, device_address);     // X: registers 0x08, 0x09
    imu_raw_data->acc_raw.y = read_16_bit_LSB_MSB(ACC_DATA_START + 2, device_address); // Y: registers 0x0A, 0x0B
    imu_raw_data->acc_raw.z = read_16_bit_LSB_MSB(ACC_DATA_START + 4, device_address); // Z: registers 0x0C, 0x0D

    // Read Gyroscope data (X,Y,Z)
    imu_raw_data->gyro_raw.x = read_16_bit_LSB_MSB(GYRO_DATA_START, device_address);     // X: registers 0x14, 0x15
    imu_raw_data->gyro_raw.y = read_16_bit_LSB_MSB(GYRO_DATA_START + 2, device_address); // Y: registers 0x16, 0x17
    imu_raw_data->gyro_raw.z = read_16_bit_LSB_MSB(GYRO_DATA_START + 4, device_address); // Z: registers 0x18, 0x19

    // Read Magnetometer data (X,Y,Z)
    imu_raw_data->mag_raw.x = read_16_bit_LSB_MSB(MAG_DATA_START, device_address);     // X: registers 0x0E, 0x0F
    imu_raw_data->mag_raw.y = read_16_bit_LSB_MSB(MAG_DATA_START + 2, device_address); // Y: registers 0x10, 0x11
    imu_raw_data->mag_raw.z = read_16_bit_LSB_MSB(MAG_DATA_START + 4, device_address); // Z: registers 0x12, 0x13

    // Read Euler angles (Roll, Pitch, Heading)
    imu_raw_data->euler_raw.z = read_16_bit_LSB_MSB(EULER_DATA_START, device_address);     // Heading: registers 0x1E, 0x1F
    imu_raw_data->euler_raw.x = read_16_bit_LSB_MSB(EULER_DATA_START + 2, device_address); // Roll: registers 0x1A, 0x1B
    imu_raw_data->euler_raw.y = read_16_bit_LSB_MSB(EULER_DATA_START + 4, device_address); // Pitch: registers 0x1C, 0x1D

    // Read Quaternion data (W,X,Y,Z)
    imu_raw_data->quaternion_raw.w = read_16_bit_LSB_MSB(QUATERNION_DATA_START, device_address);     // W: registers 0x20, 0x21
    imu_raw_data->quaternion_raw.x = read_16_bit_LSB_MSB(QUATERNION_DATA_START + 2, device_address); // X: registers 0x22, 0x23
    imu_raw_data->quaternion_raw.y = read_16_bit_LSB_MSB(QUATERNION_DATA_START + 4, device_address); // Y: registers 0x24, 0x25
    imu_raw_data->quaternion_raw.z = read_16_bit_LSB_MSB(QUATERNION_DATA_START + 6, device_address); // Z: registers 0x26, 0x27
}

/*#############################################################################################################*/
/**
 * @brief Convert raw IMU sensor data to real-world units
 * @param imu_raw_data Input raw sensor data from BNO055
 * @param imu_real_data Pointer to structure where converted data will be stored
 *
 * This function converts all raw sensor data from BNO055 to their corresponding real-world units:
 * - Accelerometer: Converts from LSB to g (gravity), where 1000 LSB = 1g
 * - Gyroscope: Converts from LSB to degrees/second, where 16 LSB = 1°/s
 * - Magnetometer: Converts from LSB to microTesla, where 16 LSB = 1µT
 * - Euler angles: Converts from LSB to degrees, where 16 LSB = 1°
 * - Quaternion: Converts from LSB to quaternion units, where 16384 LSB = 1 unit
 */
/*#############################################################################################################*/

void convert_IMU_raw_data_to_real_local_data(IMU_Raw_Data* imu_raw_data, IMU_Real_local_Data *imu_real_local_data)
{
    // Convert Accelerometer data
    // LSB/mg (milli-g)
    // Range ±2g: 1m/s^2 = 100 LSB
    imu_real_local_data->acc_local_real.x = imu_raw_data->acc_raw.x / 1000.0; // Convert to g
    imu_real_local_data->acc_local_real.y = imu_raw_data->acc_raw.y / 1000.0; // Convert to g
    imu_real_local_data->acc_local_real.z = imu_raw_data->acc_raw.z * 0.0098; // Convert to g

    // Convert Gyroscope data
    // LSB/dps (degrees per second)
    // Range ±2000°/s: 1°/s = 16 LSB
    imu_real_local_data->gyro_local_real.x = imu_raw_data->gyro_raw.x * 0.0625; // Convert to degrees/s
    imu_real_local_data->gyro_local_real.y = imu_raw_data->gyro_raw.y * 0.0625; // Convert to degrees/s
    imu_real_local_data->gyro_local_real.z = imu_raw_data->gyro_raw.z * 0.0625; // Convert to degrees/s

    // Convert Magnetometer data
    // LSB/µT (microTesla)
    // Range ±1300µT: 1µT = 16 LSB
    imu_real_local_data->mag_local_real.x = imu_raw_data->mag_raw.x / 16.0; // Convert to microTesla
    imu_real_local_data->mag_local_real.y = imu_raw_data->mag_raw.y / 16.0; // Convert to microTesla
    imu_real_local_data->mag_local_real.z = imu_raw_data->mag_raw.z / 16.0; // Convert to microTesla

    // Convert Euler Angles data
    // LSB/degree
    // Range: Heading/Yaw(z): 0° to 360° (Rotation around Z-axis, points to North)
    //        Roll(x): -90° to +90° (Rotation around X-axis, positive = tilt right)
    //        Pitch(y): -180° to +180° (Rotation around Y-axis, positive = tilt up)
    // Earth Frame Reference:
    //        X-axis: Points to East
    //        Y-axis: Points to North
    //        Z-axis: Points Up (opposite to gravity)
    // 1° = 16 LSB
    imu_real_local_data->euler_real.x = imu_raw_data->euler_raw.x / 16.0; // Convert to degrees (Roll)
    imu_real_local_data->euler_real.y = imu_raw_data->euler_raw.y / 16.0; // Convert to degrees (Pitch)
    imu_real_local_data->euler_real.z = imu_raw_data->euler_raw.z / 16.0; // Convert to degrees (Yaw/Heading)

    // Convert Quaternion data
    // LSB/quaternion unit
    // Range: 1 quaternion unit = 2^14 LSB = 16384 LSB
    imu_real_local_data->quaternion_real.w = imu_raw_data->quaternion_raw.w / 16384.0; // Convert to quaternion unit
    imu_real_local_data->quaternion_real.x = imu_raw_data->quaternion_raw.x / 16384.0; // Convert to quaternion unit
    imu_real_local_data->quaternion_real.y = imu_raw_data->quaternion_raw.y / 16384.0; // Convert to quaternion unit
    imu_real_local_data->quaternion_real.z = imu_raw_data->quaternion_raw.z / 16384.0; // Convert to quaternion unit
}

/*#############################################################################################################*/
/**
 * @brief Calculate the inverse of a quaternion
 * @param quar Input quaternion to be inverted
 * @return Inverted quaternion
 *
 * This function calculates the inverse of a quaternion by dividing each component by the quaternion's norm and
 * negating the vector components (x, y, z).
 * For a unit quaternion, this is equivalent to its conjugate.
 * Formula: q^(-1) = conjugate(q)/norm(q), where norm = w^2 + x^2 + y^2 + z^2
 */
/*#############################################################################################################*/

Real_quaternion quaternion_inverse(Real_quaternion qua)
{
    Real_quaternion result;
    float norm = qua.w * qua.w + qua.x * qua.x + qua.y * qua.y + qua.z * qua.z;
    result.w = qua.w / norm;
    result.x = -qua.x / norm;
    result.y = -qua.y / norm;
    result.z = -qua.z / norm;
    return result;
}

/*#############################################################################################################*/
/**
 * @brief Multiply two quaternions together
 * @param qua_1 First quaternion operand
 * @param qua_2 Second quaternion operand
 * @return Result of quaternion multiplication
 *
 * This function performs quaternion multiplication using the Hamilton product rule.
 * For two quaternions q1 = (w1,x1,y1,z1) and q2 = (w2,x2,y2,z2), their product is:
 * w = w1*w2 - x1*x2 - y1*y2 - z1*z2
 * x = w1*x2 + x1*w2 + y1*z2 - z1*y2
 * y = w1*y2 - x1*z2 + y1*w2 + z1*x2
 * z = w1*z2 + x1*y2 - y1*x2 + z1*w2
 */
/*#############################################################################################################*/

Real_quaternion quarternion_multiply(Real_quaternion qua_1, Real_quaternion qua_2)
{
    Real_quaternion result;
    result.w = qua_1.w * qua_2.w - qua_1.x * qua_2.x - qua_1.y * qua_2.y - qua_1.z * qua_2.z;
    result.x = qua_1.w * qua_2.x + qua_1.x * qua_2.w + qua_1.y * qua_2.z - qua_1.z * qua_2.y;
    result.y = qua_1.w * qua_2.y - qua_1.x * qua_2.z + qua_1.y * qua_2.w + qua_1.z * qua_2.x;
    result.z = qua_1.w * qua_2.z + qua_1.x * qua_2.y - qua_1.y * qua_2.x + qua_1.z * qua_2.w;
    return result;
}

/*#############################################################################################################*/
/**
 * @brief Rotate a vector by a quaternion
 * @param vec Input vector to be rotated
 * @param quar Quaternion representing the rotation
 * @return Rotated vector
 *
 * This function rotates a 3D vector by a quaternion using the formula:
 * v' = q * v_quat * q^-1
 * where v' is the rotated vector, q is the rotation quaternion, and v_quat is the input vector converted to a
 * quaternion.
 * The quaternion inverse is calculated to reverse the rotation after the multiplication.
 * The result is then converted back to a 3D vector, but converted to global coordinates.
 */
/*#############################################################################################################*/

Real_vector3 rotate_vector_by_quarternion(Real_vector3 vec, Real_quaternion qua)
{
    Real_quaternion v_qua = {0, vec.x, vec.y, vec.z}; // Convert vector to quaternion
    Real_quaternion q_inv = quaternion_inverse(qua);  // Calculate inverse of quaternion

    // Perform rotation: v' = q * v_quat * q^-1
    Real_quaternion v_rotated = quarternion_multiply(quarternion_multiply(qua, v_qua), q_inv);

    // Convert result back to vector
    Real_vector3 result;
    result.x = v_rotated.x;
    result.y = v_rotated.y;
    result.z = v_rotated.z;

    return result;
}

/*#############################################################################################################*/
/**
 * @brief Convert IMU data from local (sensor) coordinates to global (Earth) coordinates
 * @param imu_local_data Input IMU data in local coordinate system
 * @param imu_global_data Pointer to structure where global coordinate data will be stored
 *
 * This function converts IMU sensor readings from the local coordinate frame (sensor's perspective)
 * to the global coordinate frame (Earth's reference) using quaternion rotation:
 *
 * Local (Sensor) Frame:
 * - Represents measurements relative to how sensor is oriented
 * - Changes with sensor movement/orientation
 * - X,Y,Z axes aligned with sensor's physical orientation
 *
 * Global (Earth) Frame:
 * - X-axis: Points East
 * - Y-axis: Points North
 * - Z-axis: Points Up (opposite to gravity)
 * - Fixed reference frame regardless of sensor orientation
 *
 * Conversion is necessary to:
 * - Get consistent measurements regardless of sensor orientation
 * - Reference measurements to Earth's coordinate system
 * - Enable proper navigation and orientation tracking
 *
 * Uses quaternion rotation: v_global = q * v_local * q^(-1)
 * where q is the orientation quaternion from BNO055
 *
 * Euler angles are copied directly as they are already in global frame
 * Quaternion data is not use anymore
 */
/*#############################################################################################################*/

void convert_IMU_local_data_to_global_data(IMU_Real_local_Data imu_real_local_data, IMU_Data *imu_real_global_data)
{
    // Convert Accelerometer data to global frame
    imu_real_global_data->acc = rotate_vector_by_quarternion(imu_real_local_data.acc_local_real, imu_real_local_data.quaternion_real);

    // Convert Gyroscope data to global frame
    imu_real_global_data->gyro = rotate_vector_by_quarternion(imu_real_local_data.gyro_local_real, imu_real_local_data.quaternion_real);

    // Convert Magnetometer data to global frame
    imu_real_global_data->mag = rotate_vector_by_quarternion(imu_real_local_data.mag_local_real, imu_real_local_data.quaternion_real);

    // Copy Euler angles data directly
    imu_real_global_data->euler = imu_real_local_data.euler_real;
}

/*#############################################################################################################*/
/**
 * @brief Read IMU sensor data and convert to global coordinates
 * @param imu_data Pointer to structure where global IMU data will be stored
 *
 * This function reads raw sensor data from BNO055, converts it to real-world units, then converts it from
 * local (sensor) coordinates to global (Earth) coordinates.
 * The final IMU data is stored in the provided structure.
 */
/*#############################################################################################################*/

void read_IMU_data(IMU_Data *imu_data, uint8_t device_address)
{
    IMU_Raw_Data imu_raw_data;
    IMU_Real_local_Data imu_real_local_data;
    read_IMU_raw_data(&imu_raw_data, device_address);
    convert_IMU_raw_data_to_real_local_data(&imu_raw_data, &imu_real_local_data);
    convert_IMU_local_data_to_global_data(imu_real_local_data, imu_data);
}