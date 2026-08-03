import React, { useState, useEffect, useRef } from "react";
import LoginModal from "./LoginModal";
import { useMessage } from "./MessageModal";
import "../assets/css/LandingPage.css";
import uwbIcon from "../assets/picture/uwb-icon.png";
import {
  Settings,
  X,
  Edit3,
  Smartphone,
  Tag,
  FingerprintPattern,
  SatelliteDish,
  History,
  Trophy,
} from "lucide-react";
import axios from "axios";

function LandingPage({ isLoggedIn, onLoginSuccess, onSelectMode }) {
  const [isLoginModalOpen, setIsLoginModalOpen] = useState(false);
  const [loginModalMode, setLoginModalMode] = useState("login");

  const [showDeviceManager, setShowDeviceManager] = useState(false);
  const [rssiDevices, setRssiDevices] = useState([]);
  const [uwbDevices, setUwbDevices] = useState([]);
  const [editingDevice, setEditingDevice] = useState(null);
  const [newDeviceName, setNewDeviceName] = useState("");

  const [trainingHistory, setTrainingHistory] = useState([]);

  const { showAlert } = useMessage();

  // Flag chống gọi API 2 lần
  const hasFetchedHistory = useRef(false);

  // Hook lắng nghe thiết bị mới qua WebSocket
  useEffect(() => {
    let ws;
    if (showDeviceManager) {
      fetchDevices();

      // Mở kết nối WebSocket lắng nghe Server
      ws = new WebSocket("ws://localhost:8000/ws/devices");

      ws.onopen = () => {
        console.log("WebSocket connected for Device Management");
      };

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          if (data.type === "new_device") {
            fetchDevices();
          }
        } catch (err) {
          console.error("ERROR parse WS data:", err);
        }
      };

      ws.onerror = (error) => {
        console.error("WebSocket error:", error);
      };
    }

    // Tự động ngắt kết nối khi tắt cửa sổ Popup
    return () => {
      if (ws) {
        ws.close();
      }
    };
  }, [showDeviceManager]);

  useEffect(() => {
    if (isLoggedIn) {
      if (hasFetchedHistory.current) return;
      hasFetchedHistory.current = true;

      axios
        .get("http://localhost:8000/training_history")
        .then((res) => setTrainingHistory(res.data))
        .catch((err) => console.error("Failed to fetch history:", err));
    } else {
      // Khi đăng xuất, reset lại cờ để lần sau đăng nhập vẫn load được API
      hasFetchedHistory.current = false;
    }
  }, [isLoggedIn]);

  const openDeviceManager = async () => {
    setShowDeviceManager(true);
  };

  const openLoginModal = (mode) => {
    setIsLoginModalOpen(true);
    setLoginModalMode(mode);
  };

  const fetchDevices = async () => {
    try {
      const resRssi = await axios.get("http://localhost:8000/devices/fingerprint");
      const resUwb = await axios.get("http://localhost:8000/devices/uwb");
      setRssiDevices(resRssi.data);
      setUwbDevices(resUwb.data);
    } catch (e) {
      console.error("Failed to fetch devices", e);
    }
  };

  const handleRenameDevice = async () => {
    if (!newDeviceName.trim()) return;
    try {
      await axios.put(
        `http://localhost:8000/devices/${editingDevice.type}/${editingDevice.device_id}`,
        {
          device_name: newDeviceName,
        },
      );
      setEditingDevice(null);
      fetchDevices(); // Tải lại danh sách sau khi đổi tên
    } catch (e) {
      showAlert("Error", "Failed to rename device.", "error");
    }
  };

  const handleDeleteDevice = async (e, deviceId, type) => {
    e.stopPropagation();

    try {
      await axios.delete(`http://localhost:8000/devices/${type}/${deviceId}`);
      fetchDevices();
    } catch (e) {
      showAlert("Error", "Failed to delete device.", "error");
      console.error(e);
    }
  };

  return (
    <div className="landing">
      <LoginModal
        isOpen={isLoginModalOpen}
        onClose={() => setIsLoginModalOpen(false)}
        initialMode={loginModalMode}
        onLoginSuccess={onLoginSuccess}
      />

      <nav className="landing-nav">
        <div className="nav-brand">iPAC Lab</div>
        <div className="nav-actions">
          {!isLoggedIn ? (
            // prettier-ignore
            <>
              <button className="btn-login-nav" onClick={() => openLoginModal("login")}>Log in</button>
              <button className="btn-signup-nav" onClick={() => openLoginModal("register")}>Sign Up</button>
            </>
          ) : (
            <div className="welcome-text">Welcome to Workspace</div>
          )}
        </div>
      </nav>

      <main className="hero-content">
        <div className="hero-text-area">
          <div className="hero-subtitle">For personal project development</div>
          <h1 className="hero-title">
            Indoor
            <br />
            Positioning
            <br />
            System.
          </h1>
          <p className="hero-desc">
            Experience the most advanced indoor positioning technology powered
            by UWB trilateration and RSSI fingerprinting.
          </p>
        </div>
      </main>

      {/* Các khối màu mờ ảo bên phải (Blobs) */}
      <div className="hero-visuals">
        <div className="blob blob-1"></div>
        <div className="blob blob-2"></div>
        <div className="blob blob-3"></div>
        <div className="blob blob-4"></div>
      </div>

      {/* HIỆN 2 THẺ KHI ĐÃ ĐĂNG NHẬP THÀNH CÔNG */}
      {isLoggedIn &&
        // prettier-ignore
        <div className="landing-selection-cards">

          {/* CỘT 1: WIDGET LỊCH SỬ HUẤN LUYỆN */}
          <div className="mode-card history-card">
            <div className="history-header">
              <div className="mode-icon-box" style={{ width: 32, height: 32 }}>
                <History size={34} color="#475569" />
              </div>
              <h3 className="mode-title-small">Training History</h3>
            </div>
            
            <div className="history-list">
              {trainingHistory.length === 0 ? (
                <div style={{textAlign: 'center', color: '#94a3b8', fontSize: 13, marginTop: 20}}>
                  No training records found.
                </div>
              ) : (
                trainingHistory.map((record) => (
                  <div key={record.history_id} className="history-item">
                    <div className="hi-left">
                      <span className="hi-title">{record.trainee_name}</span>
                      <span className="hi-subtitle">
                        {new Date(record.start_time).toLocaleDateString()} • {record.device_hex_id}
                      </span>
                    </div>
                      <span className="hi-title">{record.scenario_name}</span>
                    <div className="hi-score" title="Score">
                      {record.score}
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>
          <div className="mode-cards-column">
            {/* Widget RSSI Fingerprinting */}
            <div className="mode-card small-card" onClick={() => onSelectMode("fingerprint")}>
              <div className="mode-icon-box">
                <FingerprintPattern size={34} color="#475569" />
              </div>
              <div className="mode-title-small">RSSI<br />Fingerprinting</div>
            </div>

            {/* Widget UWB Trilateration và Manage Devices */}
            <div className="mode-cards-row">
              {/* Widget UWB */}
              <div className="mode-card small-card" onClick={() => onSelectMode("uwb")}>
                <div className="mode-icon-box">
                  {/* <img src={uwbIcon} alt="icon" /> */}
                  <SatelliteDish size={34} color="#475569" />
                </div>
                <div className="mode-title-small">UWB<br />Trilateration</div>
              </div>

              {/* Widget Manage Devices */}
              <div className="mode-card small-card" onClick={openDeviceManager}>
                <div className="mode-icon-box" style={{ background: "transparent", border: "none" }}>
                  <Settings size={34} color="#475569" />
                </div>
                <div className="mode-title-small">Manage<br />Devices</div>
              </div>
            </div>
          </div>
        </div>}

      {/* POPUP FULLSCREEN: DEVICE MANAGER */}
      {showDeviceManager && (
        <div className="dm-overlay">
          <div className="dm-modal">
            <button
              className="dm-close-btn"
              onClick={() => setShowDeviceManager(false)}
            >
              <X size={24} />
            </button>
            <h2 className="dm-title">Device Management</h2>

            <div className="dm-sections">
              {/* CỘT RSSI */}
              <div className="dm-column">
                <h3 className="dm-subtitle">RSSI Tags</h3>
                <div className="dm-grid">
                  {rssiDevices.map((dev) => (
                    <div
                      className="dm-device-card"
                      key={`rssi-${dev.device_id}`}
                      onClick={() => {
                        setEditingDevice({ ...dev, type: "rssi" });
                        setNewDeviceName(dev.device_name);
                      }}
                    >
                      <button
                        className="dm-btn-delete"
                        onClick={(e) =>
                          handleDeleteDevice(e, dev.device_id, "rssi")
                        }
                        title="Delete Device"
                      >
                        <X size={16} />
                      </button>
                      <div className="dm-device-icon">
                        <Smartphone size={32} color="#3b82f6" />
                      </div>
                      <div className="dm-device-info">
                        <h4>{dev.device_name}</h4>
                        <p>HEX: {dev.device_hex_id}</p>
                      </div>
                    </div>
                  ))}
                  {rssiDevices.length === 0 && (
                    <p className="dm-empty">No RSSI tags found</p>
                  )}
                </div>
              </div>

              {/* CỘT UWB */}
              <div className="dm-column">
                <h3 className="dm-subtitle">UWB Tags</h3>
                <div className="dm-grid">
                  {uwbDevices.map((dev) => (
                    <div
                      className="dm-device-card"
                      key={`uwb-${dev.device_id}`}
                      onClick={() => {
                        setEditingDevice({ ...dev, type: "uwb" });
                        setNewDeviceName(dev.device_name);
                      }}
                    >
                      <button
                        className="dm-btn-delete"
                        onClick={(e) =>
                          handleDeleteDevice(e, dev.device_id, "uwb")
                        }
                        title="Delete Device"
                      >
                        <X size={16} />
                      </button>

                      <div className="dm-device-icon">
                        <Tag size={32} color="#10b981" />
                      </div>
                      <div className="dm-device-info">
                        <h4>{dev.device_name}</h4>
                        <p>HEX: {dev.device_hex_id}</p>
                      </div>
                    </div>
                  ))}
                  {uwbDevices.length === 0 && (
                    <p className="dm-empty">No UWB tags found</p>
                  )}
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* POPUP NHỎ: ĐỔI TÊN THIẾT BỊ */}
      {editingDevice && (
        <div className="dm-rename-overlay">
          <div className="dm-rename-modal">
            <h3>
              <Edit3
                size={20}
                style={{ marginRight: "8px", verticalAlign: "middle" }}
              />{" "}
              Rename Device
            </h3>
            <p>
              HEX ID: <strong>{editingDevice.device_hex_id}</strong>
            </p>
            <input
              className="dm-input"
              value={newDeviceName}
              onChange={(e) => setNewDeviceName(e.target.value)}
              placeholder="Enter new device name"
            />
            <div className="dm-rename-actions">
              <button className="dm-btn-save" onClick={handleRenameDevice}>
                Save
              </button>
              <button
                className="dm-btn-cancel"
                onClick={() => setEditingDevice(null)}
              >
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}

      <div className="landing-nav">
        <div></div>
        <div className="powered">Powered by Son</div>
      </div>
    </div>
  );
}

export default LandingPage;
