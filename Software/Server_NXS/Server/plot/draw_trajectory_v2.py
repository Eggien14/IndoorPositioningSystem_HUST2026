import os
import sys
import pandas as pd
import matplotlib
matplotlib.use('Agg') # Bắt buộc dùng Agg khi chạy ngầm
import matplotlib.pyplot as plt
from datetime import datetime

# Lấy thư mục gốc (tùy chỉnh lại đường dẫn cho đúng với project của bạn)
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# Thay tên file CSV thành tên file thực tế của bạn
CSV_PATH = os.path.join(ROOT_DIR, 'trajectory_data', 'map_17_26_06_2026_14_23_27.csv') 
OUTPUT_DIR = os.path.join(ROOT_DIR, 'graphs')

def main():
    if not os.path.exists(CSV_PATH):
        print(f"[Error] Trajectory CSV file not found at: {CSV_PATH}")
        sys.exit(1)

    df = pd.read_csv(CSV_PATH)
    if df.empty:
        print("[Error] Trajectory CSV file is empty.")
        sys.exit(1)

    # 1. Lọc bỏ các giá trị tọa độ âm (chỉ giữ lại position_x >= 0 và position_y >= 0)
    # ĐÃ SỬA: Cập nhật tên cột theo chuẩn file CSV mới
    df = df[(df['position_x'] >= 0) & (df['position_y'] >= 0)]
    
    if df.empty:
        print("[Error] No positive coordinates left to plot after filtering.")
        sys.exit(1)

    # Đảm bảo thư mục graphs tồn tại
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    fig, ax = plt.subplots(figsize=(6, 11)) # Điều chỉnh tỷ lệ khung ảnh cho phù hợp với 5x10
    
    colors = ['#3b82f6', '#8b5cf6', '#10b981', '#ef4444', '#f59e0b']
    
    # Nhóm theo tag_hex_id (thay vì tag_id) và vẽ từng đường
    for idx, (tag, group) in enumerate(df.groupby("tag_hex_id")):
        color = colors[idx % len(colors)]
        
        # Sửa nét đứt thành nét liền (linestyle='-') và tăng độ dày (linewidth=3.0)
        ax.plot(group['position_x'], group['position_y'], marker='o', markersize=4, linestyle='-', 
                linewidth=3.0, color=color, alpha=0.8, label=f"Tag: {tag}")
        
        # Đánh dấu điểm Đầu (Xanh) và Cuối (Đỏ)
        ax.plot(group['position_x'].iloc[0], group['position_y'].iloc[0], marker='s', markersize=8, color='green')
        ax.plot(group['position_x'].iloc[-1], group['position_y'].iloc[-1], marker='X', markersize=8, color='red')

    ax.set_xlabel('X Coordinate (m)', fontsize=12)
    ax.set_ylabel('Y Coordinate (m)', fontsize=12)
    
    # Fix cứng tọa độ trục X (0 -> 5) và Y (0 -> 10)
    ax.set_xlim(0, 5)
    ax.set_ylim(0, 10)
    
    # Chia lưới đúng 1 đơn vị = 1m cho cả 2 trục
    ax.set_xticks(range(0, 6))
    ax.set_yticks(range(0, 11))
    
    ax.grid(True, linestyle='--', alpha=0.6)
    
    # Ép khung đồ thị theo đúng tỷ lệ thực (adjustable='box' để nó không tự scale)
    ax.set_aspect('equal', adjustable='box')
    ax.legend(loc='upper right')
    
    plt.tight_layout()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    save_path = os.path.join(OUTPUT_DIR, f"trajectory_{timestamp}.png")
    plt.savefig(save_path, dpi=300, bbox_inches='tight')
    plt.close('all') 
    
    print(f"[Success] Image saved at {save_path}")

if __name__ == "__main__":
    main()