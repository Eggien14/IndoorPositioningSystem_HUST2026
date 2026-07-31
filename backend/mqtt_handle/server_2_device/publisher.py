"""Server -> Device MQTT publishers.

Đóng gói các tin nhắn server gửi về thiết bị, tuân thủ chặt chẽ schema trong
`Source/mqtt_topic.txt` (mục SERVER TO DEVICE):

- Vị trí người dùng:  topic `user_pos/<tag_id>`   -> {x, y, score}
- Firefighting data:  topic `fire_data`           -> {fires_num, fires:[{x,y,level}]}

Tất cả publish đi qua `mqtt_client` (singleton, broker hard-code trong mqtt_client.py).
`publish` trả về False nếu broker chưa kết nối.
"""
from __future__ import annotations

import json
from typing import Any, Dict, List

from backend.mqtt_client import mqtt_client


def _normalize_hex(value: str) -> str:
    value = str(value).strip().lower()
    if not value.startswith("0x"):
        value = f"0x{value}"
    return value


def _topic_hex_variants(value: str) -> List[str]:
    """Các biến thể hex cho topic user_pos (MQTT phân biệt hoa/thường + padding)."""
    raw = str(value).strip()
    norm = _normalize_hex(raw)
    variants = {raw, norm, norm.upper().replace("0X", "0x")}
    try:
        number = int(norm, 16)
        minimal = f"0x{number:x}"
        padded2 = f"0x{number:02x}"
        variants.add(minimal)
        variants.add(minimal.upper().replace("0X", "0x"))
        variants.add(padded2)
        variants.add(padded2.upper().replace("0X", "0x"))
        minimal_no_prefix = f"{number:x}"
        padded2_no_prefix = f"{number:02x}"
        variants.add(minimal_no_prefix)
        variants.add(minimal_no_prefix.upper())
        variants.add(padded2_no_prefix)
        variants.add(padded2_no_prefix.upper())
    except ValueError:
        pass
    return sorted(variants)


def publish_user_pos(tag_hex_id: str, x: float, y: float, score: int = 0) -> bool:
    """Gửi vị trí định vị về cho một thiết bị (topic `user_pos/<tag_id>`).

    Publish lên mọi biến thể hex (0xC0 / 0xc0 / C0 / c0 ...) vì firmware và MQTTX
    thường subscribe một dạng cố định trong khi server có thể giữ casing khác từ DB.
    """
    payload = json.dumps({
        "x": round(float(x), 3),
        "y": round(float(y), 3),
        "score": int(score),
    })
    ok = False
    for hex_variant in _topic_hex_variants(tag_hex_id):
        if mqtt_client.publish(f"user_pos/{hex_variant}", payload):
            ok = True
    return ok


def publish_fire_data(fires_num: int, fires: List[Dict[str, Any]]) -> bool:
    """Gửi toàn bộ ngọn lửa đang tồn tại (gốc + lan) về thiết bị (topic `fire_data`).

    Mỗi phần tử `fires`: {x:int, y:int, level:int(0-5)} — toạ độ góc dưới-trái ô.
    (Dùng ở Pha B — engine lan/dập lửa.)
    """
    payload = json.dumps({
        "fires_num": int(fires_num),
        "fires": [
            {"x": int(f["x"]), "y": int(f["y"]), "level": int(f["level"])}
            for f in fires
        ],
    })
    return mqtt_client.publish("fire_data", payload)
