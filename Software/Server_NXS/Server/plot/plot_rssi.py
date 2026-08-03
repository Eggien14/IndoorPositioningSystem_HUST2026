import os
import matplotlib
matplotlib.use('Agg') # ---> FIX LỖI 1: Ép Matplotlib chạy ngầm, không mở GUI
import matplotlib.pyplot as plt
import pandas as pd
from datetime import datetime

def plot_before_after_rssi(df_raw: pd.DataFrame, df_filtered: pd.DataFrame, output_dir: str = "graphs"):
    """
    Hàm vẽ đồ thị so sánh RSSI Trước và Sau khi qua bộ lọc WBO.
    """
    os.makedirs(output_dir, exist_ok=True)
    fig, axes = plt.subplots(2, 2, figsize=(15, 10), sharex=True)
    
    # ---> FIX LỖI 2: TRÍCH XUẤT CỘT ĐỘNG (Xử lý trường hợp df_filtered bị mất Header)
    filtered_cols = df_filtered.columns.tolist()
    raw_cols = df_raw.columns.tolist()

    def get_filtered_cols(prefix, is_wifi):
        # 1. Thử tìm bằng tên (Nếu file CSV sau khi lọc còn giữ Header)
        cols = [c for c in filtered_cols if prefix in str(c).lower()]
        if len(cols) >= 4:
            return cols[:4]
        
        # 2. Fallback: Nếu file bị mất Header và mất 2 cột tọa độ
        # Wi-Fi luôn nằm ở 4 cột đầu (0-3), BLE luôn nằm ở 4 cột sau (4-7)
        if is_wifi:
            return filtered_cols[0:4]
        else:
            return filtered_cols[4:8]

    wf_cols = get_filtered_cols('wifi', True)
    bl_cols = get_filtered_cols('ble', False)
    SAMPLE_LIMIT = 30
    df_raw = df_raw.head(SAMPLE_LIMIT)
    df_filtered = df_filtered.head(SAMPLE_LIMIT)

    # ==========================================
    # HÀNG 1: WI-FI RSSI
    # ==========================================
    if 'rssi_wifi_1' in df_raw.columns:
        # Cột Trái: Raw Wi-Fi
        for i, col in enumerate(['rssi_wifi_1', 'rssi_wifi_2', 'rssi_wifi_3', 'rssi_wifi_4']):
            axes[0, 0].plot(df_raw.index, df_raw[col], label=f'AP {i+1}', alpha=0.8)
        axes[0, 0].set_title('Raw Wi-Fi RSSI (Before)', fontsize=13, fontweight='bold')
        axes[0, 0].set_ylabel('RSSI (dBm)', fontsize=11)
        axes[0, 0].grid(True, linestyle='--', alpha=0.5)
        
        # Cột Phải: Filtered Wi-Fi
        for i, col in enumerate(wf_cols):
            axes[0, 1].plot(df_filtered.index, df_filtered[col], label=f'AP {i+1}', linewidth=1.5)
        axes[0, 1].set_title('Filtered Wi-Fi RSSI (After WBO)', fontsize=13, fontweight='bold')
        axes[0, 1].grid(True, linestyle='--', alpha=0.5)
        axes[0, 1].legend(loc='lower right')

    # ==========================================
    # HÀNG 2: BLE RSSI
    # ==========================================
    if 'rssi_ble_1' in df_raw.columns:
        # Cột Trái: Raw BLE
        for i, col in enumerate(['rssi_ble_1', 'rssi_ble_2', 'rssi_ble_3', 'rssi_ble_4']):
            axes[1, 0].plot(df_raw.index, df_raw[col], label=f'BLE {i+1}', alpha=0.8)
        axes[1, 0].set_title('Raw BLE RSSI (Before)', fontsize=13, fontweight='bold')
        axes[1, 0].set_ylabel('RSSI (dBm)', fontsize=11)
        axes[1, 0].set_xlabel('Samples', fontsize=11)
        axes[1, 0].grid(True, linestyle='--', alpha=0.5)

        # Cột Phải: Filtered BLE
        for i, col in enumerate(bl_cols):
            axes[1, 1].plot(df_filtered.index, df_filtered[col], label=f'BLE {i+1}', linewidth=1.5)
        axes[1, 1].set_title('Filtered BLE RSSI (After WBO)', fontsize=13, fontweight='bold')
        axes[1, 1].set_xlabel('Samples', fontsize=11)
        axes[1, 1].grid(True, linestyle='--', alpha=0.5)
        axes[1, 1].legend(loc='lower right')

    # Căn chỉnh và lưu file
    plt.tight_layout()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"wbo_comparison_{timestamp}.png"
    save_path = os.path.join(output_dir, filename)
    plt.savefig(save_path, dpi=300, bbox_inches='tight')
    
    # Giải phóng hoàn toàn bộ nhớ sau khi vẽ xong
    plt.close('all') 
    
    print(f"✅ Comparison graph has been drawn and saved at: {save_path}")
    return save_path