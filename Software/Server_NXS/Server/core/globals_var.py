import os



ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

data_queue = None               # Queue lưu dữ liệu RSSI từ MQTT để phục vụ API collect data

ai_predictor = None             # Object Model AI load vào RAM

mqtt_client = None              # Đối tượng mqtt client

# List các client (ReactJS) đang kết nối Websocket
active_websockets = []
device_manager_websockets = []

rssi_buffers = {}               # Buffer tối đa 10 phần tử RSSI reality cho AI dự đoán

uwb_distance_buffer = {}        # Buffer gom khoảng cách từ các beacon cho từng Tag theo chiều dọc tin nhắn MQTT

BEACONS_CONFIG = {}             # Biến Cache lưu tọa độ Beacon

uwb_trackers = {}               # Biến lưu trữ thông tin về các tracker UWB

# Set theo dõi xem thiết bị đã được lưu vào DB chưa
KNOWN_RSSI_DEVICES = set()
KNOWN_UWB_DEVICES = set()

CURRENT_SCORES = {}             # Biến lưu trữ điểm số đồng bộ từ Frontend gửi và gửi MQTT xuống thiết bị

CURRENT_UWB_CELL_LENGTH = 1.0   # Biến cache lưu chiều dài cạnh 1 ô vuông của map

CURRENT_MAP_NORTH_OFFSET = 90.0 # Biến cache lưu góc lệch về hướng Bắc của map

db_buffer_uwb = []              # Buffer để lưu trữ dữ liệu UWB trước khi ghi vào DB

db_buffer_rssi = []             # Buffer để lưu trữ dữ liệu RSSI trước khi ghi vào DB

kalman_filters = {}             # Biến lưu trữ các bộ lọc Kalman

step_detectors = {}             # Biến lưu trữ các bộ đếm bước chân

pdr_fusion_trackers = {}        # Biến lưu trữ các bộ fusion PDR