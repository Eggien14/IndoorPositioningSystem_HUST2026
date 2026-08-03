## 1. Topic: MQTT_USER_POS_TOPIC

**Topic** user_pos/0xC0

**MQTT cmd** mosquitto_pub -h "192.168.1.247" -p 1883 -t "user_pos/0xC0" -m ""

**Test_1**
{
  "x": 2.5,
  "y": 4.8,
  "score": 150
}

{
    "x": <Tọa độ x>(float), 
    "y": <Tọa độ y>(float),
    "score": <Điểm số huấn luyện>(int)
}


mosquitto_pub -h "192.168.1.247" -p 1883 -t "user_pos/0xC0" -m "{"x": 2.5,"y": 4.8,"score": 150}"
**Test_2**
{
  "x": 3.7,
  "y": 6.1,
  "score": 250
}

mosquitto_pub -h "192.168.1.247" -p 1883 -t "user_pos/0xC0" -m "{"x": 3.7,"y": 6.1,"score": 250}
## 2. Topic: MQTT_MAP_DATA_TOPIC

**Topic** map_data

**MQTT cmd** mosquitto_pub -h "192.268.1.247" -p 1883 -t "map_data" -m ""

**Test_1**
{
  "info": {
    "x": 8,
    "y": 9,
    "north_offset": 0.0
  },
  "cells": [
    [0,0],[1,0],[2,0],[3,0],[4,0],[0,1],[1,1],[2,1],
    [3,1],[4,1],[0,2],[1,2],[2,2],[3,2],[4,2],[0,3],
    [1,3],[2,3],[3,3],[4,3],[0,4],[1,4],[2,4],[3,4],
    [4,4],[0,5],[1,5],[2,5],[3,5],[4,5],[0,6],[1,6],
    [2,6],[3,6],[4,6],[0,7],[1,7],[2,7],[3,7],[4,7],
    [0,8],[1,8],[2,8],[3,8],[4,8],[0,9],[1,9]
  ]
}

{
  "info": {
    "x": <kích thước map theo chiều ngang(mét)>(int),
    "y": <kích thước map theo chiều dọc(mét)>(int),
    "north_offset": <Góc Offset Bắc>(float)
  },
  "cells": [
    [x_1, y_1], <Tọa độ góc dưới cùng bên trái ô đi được>(<Array int>),
    [x_2, y_2],
    ....
    [x_n, y_n],
  ]
}

mosquitto_pub -h "192.168.1.247" -p 1883 -t "map_data" -m "{"info": {"x": 8,"y": 9,"north_offset": 0.0},"cells": [[0, 0], [1, 0], [2, 0], [3, 0], [0, 1], [0, 2], [0, 3], [8, 6],[5, 5], [5, 6], [6, 5], [6, 6],[3, 6], [2, 4], [7, 8], [8, 7],[1, 2], [1, 3], [1, 4], [1, 5],[2, 2], [2, 3], [2, 7], [2, 5],[3, 3], [3, 3], [3, 4], [3, 5]]}"

## 2. Topic: MQTT_FLAMES_DATA_TOPIC
**Topic** fire_data

**MQTT cmd** mosquitto_pub -h "192.168.1.247" -p 1883 -t "fire_data" -m ""

**Test_1**
{
  "fires_num": 3,
  "fires": [
    { "x": 1, "y": 1, "level": 1 },
    { "x": 5, "y": 5, "level": 3 },
    { "x": 8, "y": 8, "level": 5 }
  ]
}

**Test_2**
{
  "fires_num": 3,
  "fires": [
    { "x": 1, "y": 1, "level": 0 },
    { "x": 5, "y": 5, "level": 0 },
    { "x": 8, "y": 8, "level": 0 }
  ]
}



**Test_2**

{
  "fires_num": <Tổng số ngọn lửa đang xuất hiện>(int),
  "fires": [
    {"x": <Tọa độ x ô có ngọn lựa, dưới cùng bên trái>(int), 
      "y": <Tọa độ y ô có ngọn lựa, dưới cùng bên trái>(int),
      "level": <Mức ngọn lửa từ 0 đến 5>(int)},
  ...
  ]
}



{
  "fires_num": 5,
  "fires": [
    { "x": 3, "y": 4, "level": 1 },
    { "x": 5, "y": 6, "level": 2 },
    { "x": 1, "y": 2, "level": 3 },
    { "x": 7, "y": 8, "level": 4 },
    { "x": 9, "y": 10, "level": 5 }
  ]
}


## 2. Topic: DEVICE_DATA
**Test_1**
{  
  "bno": {
    "acc": {
        "x": <Gia tốc theo trục X>(float),
        "y": <Gia tốc theo trục Y>(float),  
        "z": <Gia tốc theo trục Z>(float)
    }, 
    "gyro": {
        "x": <Tốc độ góc theo trục X>(float),
        "y": <Tốc độ góc theo trục Y>(float),  
        "z": <Tốc độ góc theo trục Z>(float)
    },
    "mag": {
        "x": <Từ trường theo trục X>(float),
        "y": <Từ trường theo trục Y>(float),  
        "z": <Từ trường theo trục Z>(float)
    },
    "euler": {
        "yaw": <Góc yaw>(float),
        "roll": <Góc roll>(float),  
        "pitch": <Góc pitch>(float)
    }
  },
  "valve": {
    "open": <Độ mở van %>(float),
    "mode": <Chế độ phun tia hay chùm>(float)
  },
  "button": {
    "A": <Trạng thái nút A>(bool),
    "B": <Trạng thái nút B>(bool),
    "C": <Trạng thái nút C>(bool)
  }
}
