import axios from "axios";
import React, { useState, useEffect, useRef } from "react";
import {
  Wifi,
  WifiOff,
  ArrowLeft,
  Play,
  X,
  Flame,
  Pause,
  Timer,
  Trophy,
  FireExtinguisher,
  AlertTriangle,
} from "lucide-react";
import "../assets/css/RealtimeMonitor.css";
import { useMessage } from "./MessageModal";
import fire1Icon from "../assets/picture/fire_1.svg";
import fire2Icon from "../assets/picture/fire_2.svg";
import fire3Icon from "../assets/picture/fire_3.svg";
import fireSpread1Icon from "../assets/picture/flames_1.svg";
import fireSpread2Icon from "../assets/picture/flames_2.svg";
import fireSpread3Icon from "../assets/picture/flames_3.svg";

const TAG_COLORS = ["#3b82f6", "#8b5cf6", "#10b981", "#ef4444", "#f59e0b"];
const CELL_SIZE = 38;

function RealtimeMonitor({ mapData, systemMode, onBack }) {
  // === STATE CƠ BẢN CỦA IPS ===
  const [wsStatus, setWsStatus] = useState("connecting");
  const [locations, setLocations] = useState({});
  const locationsRef = useRef({}); // Dùng Ref để lưu toạ độ mới nhất, phục vụ vòng lặp huấn luyện
  const hasInitialized = useRef(false);
  const [devices, setDevices] = useState([]);
  const rows = mapData.rows || 10;
  const cols = mapData.cols || 10;
  const blocked = new Set(mapData.blocked_cells || []);
  const routers = new Set(mapData.router_location || []);

  // === STATE CỦA HỆ THỐNG HUẤN LUYỆN ===
  const [scenarios, setScenarios] = useState([]);
  const [selectedScenarioId, setSelectedScenarioId] = useState("free");
  const [trainingState, setTrainingState] = useState("idle"); // "idle", "running", "finished"
  const [timeElapsed, setTimeElapsed] = useState(0);
  const [scores, setScores] = useState({}); // Lưu điểm cho từng tag
  const [traineeNames, setTraineeNames] = useState({}); // Lưu tên trainee
  const [sessionFires, setSessionFires] = useState([]); // Chứa danh sách lửa và trạng thái
  const [countdown, setCountdown] = useState(null);
  const intervalRef = useRef(null);
  const timeRef = useRef(0);
  const firesRef = useRef([]);
  const wsRef = useRef(null);
  const hasSavedHistory = useRef(false);
  const [spreadWarning, setSpreadWarning] = useState(false);
  const [showTrajectory, setShowTrajectory] = useState(false);
  const trajectoryRef = useRef({});

  const { showAlert } = useMessage();

  // 1. HOOK GỌI API LOAD MODEL & LOAD SCENARIOS
  useEffect(() => {
    if (hasInitialized.current) return;
    hasInitialized.current = true;

    let ws = null;

    const initSystem = async () => {
      try {
        // Fetch danh sách thiết bị
        const devRes = await axios.get(
          `http://localhost:8000/devices/${systemMode}`,
        );
        setDevices(devRes.data);
        // Fetch danh sách kịch bản
        const scRes = await axios.get(
          `http://localhost:8000/scenarios/${systemMode}/${mapData.map_info_id}`,
        );
        setScenarios(scRes.data);

        // Fetch map dùng model AI và UWB trilateration
        if (systemMode === "uwb") {
          await axios.post(
            `http://localhost:8000/set_active_uwb_map/${mapData.map_info_id}`,
          );
        } else if (systemMode === "fingerprint") {
          await axios.post(
            `http://localhost:8000/set_active_rssi_map/${mapData.map_info_id}`,
          );
        }

        // Kết nối WebSocket
        ws = new WebSocket("ws://localhost:8000/ws/realtime_location");
        wsRef.current = ws;
        ws.onopen = () => setWsStatus("connected");
        ws.onmessage = (event) => {
          try {
            const data = JSON.parse(event.data);
            const tagId = data.tag_id;
            if (tagId) {
              setLocations((prev) => {
                // Merge dữ liệu góc yaw vào dữ liệu tọa độ
                const newLocs = {
                  ...prev,
                  [tagId]: { ...(prev[tagId] || {}), ...data }, // Nếu packet chỉ có yaw, tọa độ x,y cũ vẫn được giữ nguyên
                };
                locationsRef.current = newLocs;
                return newLocs;
              });
            }

            // Lưu lịch sử vẽ quỹ đạo
            if (!trajectoryRef.current[data.tag_id]) {
              trajectoryRef.current[data.tag_id] = [];
            }

            const history = trajectoryRef.current[data.tag_id];
            const lastPoint =
              history.length > 0 ? history[history.length - 1] : null;

            // Chỉ lưu thêm điểm mới nếu Tag đã di chuyển một khoảng nhất định
            if (
              !lastPoint ||
              Math.abs(lastPoint.x - data.x) > 0.05 ||
              Math.abs(lastPoint.y - data.y) > 0.05
            ) {
              history.push({ x: data.x, y: data.y });

              if (history.length > 200) {
                history.shift();
              }
            }
          } catch (err) {
            console.error("WS error:", err);
          }
        };
        ws.onclose = () => setWsStatus("error");
      } catch (err) {
        showAlert(
          "Warning",
          `Setup failed for Map #${mapData?.map_info_id}. Train model first if using RSSI!`,
        );
        onBack();
      }
    };

    initSystem();
    return () => {
      if (ws) ws.close();
    };
  }, [mapData?.map_info_id, systemMode]);

  // 2. HOOK VÒNG LẶP HUẤN LUYỆN (Chạy mỗi 1 giây)
  useEffect(() => {
    if (trainingState === "running") {
      intervalRef.current = setInterval(() => {
        // Tăng time + 1s
        timeRef.current += 1;
        setTimeElapsed(timeRef.current);

        let fireStateChanged = false;
        let tagPointChanges = {};

        Object.keys(locationsRef.current).forEach((tagId) => {
          tagPointChanges[tagId] = 0;
        });

        // Xử lý logic lửa
        let newSpawnedFires = [];
        const updatedFires = firesRef.current.map((fire) => {
          if (fire.status === "extinguished") return fire;

          if (fire.status === "waiting") {
            if (timeRef.current >= fire.delay_time) {
              fireStateChanged = true;
              return { ...fire, status: "burning", burn_time: 0 };
            }
            return fire;
          }

          if (fire.status === "burning") {
            // Tăng thời gian cháy + 1s
            fire.burn_time = (fire.burn_time || 0) + 1;

            // Logic lửa lan (sau mỗi 30s)
            // prettier-ignore
            if (fire.is_spreading && fire.burn_time % 10 === 0) {
              const directions = [
                [-1, -1], [-1, 0], [-1, 1], [0, -1], [0, 1], [1, -1], [1, 0], [1, 1],
              ];

              const validAdjacent = [];

              for (let [dx, dy] of directions) {
                const nx = fire.coord_x + dx;
                const ny = fire.coord_y + dy;

                // Kiểm tra tọa độ có nằm trong Map không
                if (nx >= 0.5 && nx <= cols && ny >= 0.5 && ny <= rows) {
                  const key = `${nx.toFixed(1)}:${ny.toFixed(1)}`;

                  // Kiểm tra xem ô đó có bị block không
                  if (!blocked.has(key)) {
                    // Kiểm tra xem ô đó đã có ngọn lửa nào đang cháy không
                    const isOccupied =
                      firesRef.current.some(
                        (f) =>
                          f.coord_x === nx &&
                          f.coord_y === ny &&
                          f.status !== "extinguished",
                      ) ||
                      newSpawnedFires.some(
                        (f) => f.coord_x === nx && f.coord_y === ny,
                      );

                    if (!isOccupied) {
                      validAdjacent.push({ x: nx, y: ny });
                    }
                  }
                }
              }

              // Nếu còn ô trống, chọn Random 1 ô để lây lan
              if (validAdjacent.length > 0) {
                const target =
                  validAdjacent[
                    Math.floor(Math.random() * validAdjacent.length)
                  ];
                newSpawnedFires.push({
                  coord_x: target.x,
                  coord_y: target.y,
                  level: fire.level,
                  is_spreading: true,
                  status: "burning",
                  progress: 0,
                  burn_time: 0,
                  delay_time: 0,
                });
                fireStateChanged = true;
                setSpreadWarning(true);
              }
            }

            // LOGIC DẬP LỬA
            const tags = Object.entries(locationsRef.current).map(
              ([id, loc]) => ({ id, ...loc }),
            );

            let activeTagsForThisFire = []; // Danh sách các tag đang dập lửa này

            // Tính độ dài 1 ô vuông thực tế theo m đổi sang px
            const cellLengthMeters = Math.sqrt(mapData.area_of_one_unit || 1);

            for (const tag of tags) {
              const clampedX = Math.max(0, Math.min(cols, tag.x || 0));
              const clampedY = Math.max(0, Math.min(rows, tag.y || 0));
              const dx = fire.coord_x - clampedX;
              const dy = fire.coord_y - clampedY;
              const dist = Math.sqrt(dx * dx + dy * dy);

              // Dẫm lên lửa -> Bị trừ điểm
              if (dist <= 0.5) {
                tagPointChanges[tag.id] -= 10;
              }

              const valve = tag.valve_per !== undefined ? tag.valve_per : 0;

              // ĐIỀU KIỂN 1: Van mở
              if (valve > 0) {
                const spray = tag.spray_per !== undefined ? tag.spray_per : 100;

                // Tính toán giới hạn của hình quạt
                const sprayAngle = 15 + (spray / 100) * (60 - 15); // Góc quét
                const radiusM = 2.5 - (spray / 100) * (2.5 - 1.5); // Tầm xa
                const radiusInCells = radiusM / cellLengthMeters; // Tầm xa quy đổi theo ô vuông

                // ĐIỀU KIỆN 2: Ngọn lửa phải nằm trong tầm xa
                if (dist <= radiusInCells) {
                  // Tính góc thực tế từ Tag hướng tới Ngọn lửa
                  // Dùng atan2(dx, dy) để gốc 0 độ hướng thẳng lên (North), giống cảm biến yaw
                  let angleToFire = Math.atan2(dx, dy) * (180 / Math.PI);
                  if (angleToFire < 0) angleToFire += 360;

                  const rawYaw = tag.yaw || 0;
                  const northOffset = mapData.north_offset || 0; // Lấy từ mapData
                  const realYaw = rawYaw - northOffset;

                  // Tính độ chênh lệch góc giữa hướng Tag và hướng ngọn lửa
                  let diff = Math.abs((angleToFire - realYaw + 360) % 360);
                  if (diff > 180) diff = 360 - diff;

                  // ĐIỀU KIỆN 3: Góc từ ngọn lửa đến tag < 1/2 góc hình quạt
                  if (diff <= sprayAngle / 2) {
                    activeTagsForThisFire.push(tag.id);
                  }
                }
              }
            }

            if (activeTagsForThisFire.length > 0) {
              const requiredTimeToDrop = 3; // Thời gian giảm 1 level
              const newProgress = fire.progress + 1;

              if (newProgress >= requiredTimeToDrop) {
                fireStateChanged = true;
                const newLevel = fire.level - 1;

                const rewardPoints = fire.is_spreading ? 100 : 50;
                activeTagsForThisFire.forEach((tagId) => {
                  tagPointChanges[tagId] += rewardPoints;
                });

                if (newLevel <= 0) {
                  return {
                    ...fire,
                    status: "extinguished",
                    progress: 0,
                    level: 0,
                  };
                } else {
                  return { ...fire, level: newLevel, progress: 0 };
                }
              }
              return { ...fire, progress: newProgress };
            } else {
              // Nếu không có tag nào dập lửa
              if (fire.progress > 0) {
                // Đang xịt mà không dập khiến lửa hồi lại -> Trừ 5 điểm
                Object.keys(locationsRef.current).forEach((tagId) => {
                  tagPointChanges[tagId] -= 5;
                });
                return { ...fire, progress: 0 };
              }
            }
          }
          return fire;
        });

        // Có lửa lan -> cập nhật vào mảng
        if (newSpawnedFires.length > 0) {
          updatedFires.push(...newSpawnedFires);
        }

        // Cập nhật điểm
        setScores((prevScores) => {
          const newScores = { ...prevScores };
          Object.keys(locationsRef.current).forEach((tagId) => {
            const currentScore =
              newScores[tagId] !== undefined ? newScores[tagId] : 0;
            const change = tagPointChanges[tagId] || 0;
            newScores[tagId] = Math.max(0, currentScore + change);
          });

          // Gửi điểm mới lên WebSocket để đồng bộ với Frontend và gửi MQTT xuống thiết bị
          if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
            wsRef.current.send(
              JSON.stringify({
                type: "sync_scores",
                scores: newScores,
              }),
            );
          }
          return newScores;
        });

        // Gửi MQTT tọa độ ô chứa lửa và level
        if (fireStateChanged) {
          const activeFires = updatedFires.filter(
            (f) => f.status === "burning",
          );
          const firesArray = activeFires.map((f) => ({
            x: Math.floor(f.coord_x),
            y: Math.floor(f.coord_y),
            level: f.level,
          }));

          // Đóng gói JSON
          const payloadObj = {
            fires_num: firesArray.length,
            fires: firesArray,
          };

          axios
            .post("http://localhost:8000/fire_update", { payload: payloadObj })
            .catch((err) => console.error("MQTT Publish Error:", err));
        }

        // Kiểm tra điều kiện kết thúc bài tập
        if (updatedFires.every((f) => f.status === "extinguished")) {
          setTrainingState("finished");
        }

        // Cập nhật lại Ref và State
        firesRef.current = updatedFires;
        setSessionFires(updatedFires);
      }, 1000);
    } else {
      clearInterval(intervalRef.current);
    }

    return () => clearInterval(intervalRef.current);
  }, [trainingState, cols, mapData]);

  //3. HOOK cảnh báo lửa lan popup trên màn hình
  useEffect(() => {
    if (spreadWarning) {
      const timer = setTimeout(() => setSpreadWarning(false), 2000);
      return () => clearTimeout(timer);
    }
  }, [spreadWarning]);

  // 4. HOOK xử lý khi kết thúc bài tập
  useEffect(() => {
    if (trainingState === "finished" && !hasSavedHistory.current) {
      hasSavedHistory.current = true;
      const scoreTimeBonus = Math.max(0, 100 - timeElapsed * 1); // Điểm thưởng khi kết thúc bài tập
      showAlert(
        "Training successful!",
        "Training results have been saved to history.",
        "success",
      );

      const tagIds = Object.keys(locationsRef.current);

      Promise.all(
        tagIds.map((tagId) => {
          const trainee = traineeNames[tagId] || `Trainee_${tagId}`;
          const tagScore = (scores[tagId] || 0) + scoreTimeBonus;

          return axios.post("http://localhost:8000/training_history", {
            trainee_name: trainee,
            scenario_id: Number(selectedScenarioId),
            device_hex_id: tagId,
            time_elapsed: timeElapsed,
            score: tagScore,
          });
        }),
      ).catch((err) => console.error("Failed to save history", err));
    }
    if (trainingState === "idle") {
      hasSavedHistory.current = false;
    }
  }, [trainingState, timeElapsed, selectedScenarioId]);

  // Hàm đếm ngược 3-2-1 trước khi Start
  const handleInitiateTraining = () => {
    const tagIds = Object.keys(locations);
    // Nếu không có thiết bị nào kết nối
    if (tagIds.length === 0) {
      showAlert("Warning", "No devices connected!");
      return;
    }
    const isMissingName = tagIds.some(
      (id) => !traineeNames[id] || traineeNames[id].trim() === "",
    );
    // Nếu chưa nhập tên
    if (isMissingName) {
      showAlert(
        "Warning",
        "Please enter Trainee Name for all devices before starting!",
      );
      return;
    }
    setCountdown(3);
    let count = 3;
    const timer = setInterval(() => {
      count -= 1;
      if (count > 0) {
        setCountdown(count);
      } else {
        clearInterval(timer);
        setCountdown(null); // Tắt màn hình đếm ngược
        handleStartTraining(); // Gọi hàm chạy game thực sự
      }
    }, 1000);
  };
  // Hàm bắt đầu bài tập sau khi kết thúc đếm ngược
  const handleStartTraining = () => {
    if (selectedScenarioId === "free") return;
    const sc = scenarios.find(
      (s) => s.scenario_id === Number(selectedScenarioId),
    );
    if (!sc || sc.fires.length === 0)
      return showAlert("Error", "This scenario has no fires!", "error");

    const initializedFires = sc.fires.map((f) => ({
      ...f,
      status: "waiting",
      progress: 0,
    }));
    firesRef.current = initializedFires;
    setSessionFires(initializedFires);

    timeRef.current = 0;
    setTimeElapsed(0);

    // Set điểm 0 cho tất cả thiết bị đang hoạt động
    const initialScores = {};
    Object.keys(locationsRef.current).forEach(
      (tagId) => (initialScores[tagId] = 0),
    );
    setScores(initialScores);

    setTrainingState("running");
  };

  // Hàm kết thúc bài tập giữa chừng
  const handleAbortTraining = () => {
    if (firesRef.current.length > 0) {
      const payloadObj = {
        fires_num: 0,
        fires: [],
      };

      axios
        .post("http://localhost:8000/fire_update", {
          payload: payloadObj,
        })
        .catch((err) => console.error("Error:", err));
    }

    setTrainingState("idle");

    // Reset toàn bộ Ref và State
    firesRef.current = [];
    setSessionFires([]);
    timeRef.current = 0;
    setTimeElapsed(0);
    setScores({});
    setSelectedScenarioId("free");
  };

  // Hàm tạm dừng bài tập
  const handlePauseTraining = () => {
    setTrainingState("paused");
  };

  // Hàm tiếp tục bài tập sau khi tạm dừng
  const handleResumeTraining = () => {
    setTrainingState("running");
  };

  // === RENDER GIAO DIỆN LƯỚI ===
  const gridCells = [];
  for (let r = 0; r < rows; r++) {
    for (let c = 0; c < cols; c++) {
      const coordX = (c + 0.5).toFixed(1);
      const coordY = (rows - 1 - r + 0.5).toFixed(1);
      const key = `${coordX}:${coordY}`;
      gridCells.push(
        <div
          key={key}
          className={`map-cell monitor-cell ${blocked.has(key) ? "blocked" : ""} ${routers.has(key) ? "router-cell" : ""}`}
        >
          {routers.has(key) && <span className="router-icon">📡</span>}
        </div>,
      );
    }
  }

  const totalUnits = rows * cols - blocked.size;
  const areaM2 = rows * cols;
  const currentScenario = scenarios.find(
    (s) => s.scenario_id === Number(selectedScenarioId),
  );
  const mapName = currentScenario ? currentScenario.scenario_name : "N/A";

  return (
    <div className="rm-container">
      {/* HEADER GIỮ NGUYÊN */}
      <div
        className="rm-header"
        style={{ marginBottom: 0, paddingBottom: 0, borderBottom: "none" }}
      >
        <div className="rm-title-area">
          <button
            className="btn btn-secondary"
            onClick={onBack}
            disabled={trainingState === "running"}
          >
            <ArrowLeft size={20} />
          </button>
          <h2 className="rm-title-text">Monitor: Map #{mapData.map_info_id}</h2>
          <div className={`status-badge ${wsStatus}`}>
            {wsStatus === "connected" ? (
              <Wifi size={16} />
            ) : (
              <WifiOff size={16} />
            )}
            {wsStatus === "connected" ? "WebSocket Connected" : "Lost"}
          </div>
        </div>
        {/* Nút gạt bật/tắt quỹ đạo */}
        <label className="switch" title="Trajectory">
          <input
            type="checkbox"
            checked={showTrajectory}
            onChange={async (e) => {
              const isChecked = e.target.checked;
              setShowTrajectory(isChecked);

              if (isChecked) {
                try {
                  // 1 luồng request gọi API, API sẽ đánh thức file Python kia chạy
                  await axios.get("http://localhost:8000/trajectory/plot");
                } catch (error) {
                  console.error(
                    "Failed to call the trajectory drawing API:",
                    error,
                  );
                }
              }
            }}
          />
          <span className="slider"></span>
        </label>
      </div>

      {/* --- BỐ CỤC 2 CỘT --- */}
      <div className="dashboard-split">
        {/* ================= CỘT TRÁI: Dashboard ================= */}
        <div className="dashboard-left">
          {/* MAP INFO */}
          <div className="big-widget">
            <div className="widget-title">
              Map Info
              <span style={{ fontSize: 14 }}>
                North Offset:{" "}
                {mapData.north_offset !== undefined
                  ? mapData.north_offset + "°"
                  : "0°"}
              </span>
            </div>
            <div className="small-widgets-row">
              <div className="small-widget">
                <div className="sw-title">Name</div>
                <div className="sw-value" style={{ fontSize: 16 }}>
                  {mapName}
                </div>
              </div>
              <div className="small-widget">
                <div className="sw-title">Area</div>
                <div className="sw-value">{areaM2} m²</div>
              </div>
              <div className="small-widget">
                <div className="sw-title">Total Units</div>
                <div className="sw-value">{totalUnits}</div>
              </div>
            </div>
          </div>

          {/* CÁC THIẾT BỊ */}
          {Object.entries(locations).map(([tagId, loc], idx) => {
            const color = TAG_COLORS[idx % TAG_COLORS.length];
            const valve = loc.valve_per !== undefined ? loc.valve_per : 0;
            const spray = loc.spray_per !== undefined ? loc.spray_per : 100;

            const deviceObj = devices.find((d) => d.device_hex_id === tagId);
            const displayName = deviceObj
              ? deviceObj.device_name
              : "Unknown Device";

            return (
              <div className="big-widget" key={tagId}>
                {/* Tên thiết bị, hex id và tọa độ */}
                <div className="tag-widget-header">
                  <span className="widget-device-name">{displayName}</span>
                  <span className="widget-tag-id" style={{ color: color }}>
                    Hex_id: {tagId}
                  </span>
                  <span className="widget-coords">
                    <span style={{ marginRight: "12px" }}>
                      X:{" "}
                      <span
                        className="coord-highlight"
                        style={{ color: color }}
                      >
                        {loc.x !== undefined ? loc.x.toFixed(2) : "0.00"}
                      </span>
                    </span>
                    <span>
                      Y:{" "}
                      <span
                        className="coord-highlight"
                        style={{ color: color }}
                      >
                        {loc.y !== undefined ? loc.y.toFixed(2) : "0.00"}
                      </span>
                    </span>
                  </span>
                </div>

                {/* Ô nhập tên trainee và error/acc */}
                <div className="tag-trainee-row">
                  <div className="trainee-input-box">
                    <input
                      type="text"
                      className="trainee-input"
                      placeholder="Enter trainee name..."
                      value={traineeNames[tagId] || ""}
                      onChange={(e) =>
                        setTraineeNames({
                          ...traineeNames,
                          [tagId]: e.target.value,
                        })
                      }
                      disabled={trainingState !== "idle"}
                    />
                  </div>
                  <div className="tag-error-box">
                    <span className="coord-label-error">
                      {loc.type === "uwb" ? "Error:" : "Acc:"}
                    </span>
                    <span className="coord-val-error">
                      {loc.type === "uwb"
                        ? `${loc.error !== undefined ? loc.error : "0.0"}m`
                        : `${loc.accuracy !== undefined ? loc.accuracy : "0"}%`}
                    </span>
                  </div>
                </div>

                {/* Dashboard thông số */}
                <div className="small-widgets-row">
                  <div className="small-widget">
                    <div className="sw-title">Valve Opening</div>
                    <div
                      className="circle-prog"
                      style={{
                        background: `conic-gradient(#93c5fd 0%, #c4b5fd ${valve / 2}%, #fca5a5 ${valve}%, #f1f5f9 ${valve}%)`,
                      }}
                    >
                      <div className="circle-inner">{valve}%</div>
                    </div>
                  </div>
                  <div className="small-widget">
                    <div className="sw-title">Spray Mode</div>
                    <div
                      className="circle-prog"
                      style={{
                        background: `conic-gradient(#6ee7b7 0%, #7dd3fc ${spray / 2}%, #c4b5fd ${spray}%, #f1f5f9 ${spray}%)`,
                      }}
                    >
                      <div className="circle-inner">{spray}%</div>
                    </div>
                  </div>
                  <div className="small-widget">
                    <div className="sw-title">Device Type</div>
                    <div className="circle-prog">
                      <FireExtinguisher size={36} color="#e02f2f" />
                    </div>
                  </div>
                </div>
              </div>
            );
          })}
        </div>

        {/* ================= CỘT PHẢI: TOOLBAR VÀ MAP ================= */}
        <div className="dashboard-right">
          {/* TOOLBAR */}
          <div className="training-toolbar">
            <select
              className="input-field"
              style={{ width: "250px", margin: 0 }}
              value={selectedScenarioId}
              onChange={(e) => setSelectedScenarioId(e.target.value)}
              disabled={trainingState !== "idle"}
            >
              <option value="free">-- Select Scenario --</option>
              {scenarios.map((sc) => (
                <option key={sc.scenario_id} value={sc.scenario_id}>
                  {sc.scenario_name}
                </option>
              ))}
            </select>

            {trainingState === "running" && (
              <>
                <button
                  className="btn-outline-icon btn-outline-black"
                  onClick={handlePauseTraining}
                  title="Pause"
                >
                  <Pause size={18} />
                </button>
                <button
                  className="btn-outline-icon btn-outline-black"
                  onClick={handleAbortTraining}
                  title="End"
                >
                  <X size={18} />
                </button>
              </>
            )}

            {trainingState === "paused" && (
              <>
                <button
                  className="btn-outline-icon btn-outline-black"
                  onClick={handleResumeTraining}
                  title="Resume"
                >
                  <Play size={18} />
                </button>
                <button
                  className="btn-outline-icon btn-outline-black"
                  onClick={handleAbortTraining}
                  title="End"
                >
                  <X size={18} />
                </button>
              </>
            )}

            {trainingState === "finished" && (
              <button
                className="btn-outline-icon btn-outline-black"
                onClick={handleAbortTraining}
                title="Close"
              >
                <X size={18} />
              </button>
            )}

            {(trainingState === "running" ||
              trainingState === "paused" ||
              trainingState === "finished") && (
              <div className="training-stats">
                <div className="stat-box time-text">
                  <Timer size={16} /> {timeElapsed}s
                </div>
                {/* HIỂN THỊ DANH SÁCH SCORE THEO MÀU CỦA TỪNG TAG */}
                {Object.keys(locations).map((tagId, idx) => {
                  const tagColor = TAG_COLORS[idx % TAG_COLORS.length];
                  const currentScore =
                    scores[tagId] !== undefined ? scores[tagId] : 0;
                  return (
                    <div
                      key={`score-${tagId}`}
                      className="stat-box"
                      style={{
                        color: tagColor,
                      }}
                      title={`Score of ${tagId}`}
                    >
                      <Trophy size={16} /> {currentScore}
                    </div>
                  );
                })}
              </div>
            )}
          </div>

          {/* VẼ MAP */}
          <div className="map-grid-section">
            <div className="corner-empty"></div>
            <div
              className="x-axis-container"
              style={{
                display: "grid",
                gridTemplateColumns: `repeat(${cols}, ${CELL_SIZE}px)`,
              }}
            >
              {Array.from({ length: cols }, (_, i) => (
                <div key={`x-${i}`} className="axis-label-box">
                  <span className="axis-text">{(0.5 + i).toFixed(1)}</span>
                  <div className="axis-tick-x"></div>
                </div>
              ))}
            </div>
            <div
              className="y-axis-container"
              style={{
                display: "grid",
                gridTemplateRows: `repeat(${rows}, ${CELL_SIZE}px)`,
              }}
            >
              {Array.from({ length: rows }, (_, i) => (
                <div key={`y-${i}`} className="axis-label-box">
                  <span className="axis-text">
                    {(rows - 1 - i + 0.5).toFixed(1)}
                  </span>
                  <div className="axis-tick-y"></div>
                </div>
              ))}
            </div>

            <div
              className="map-grid"
              style={{
                gridTemplateColumns: `repeat(${cols}, ${CELL_SIZE}px)`,
                gridTemplateRows: `repeat(${rows}, ${CELL_SIZE}px)`,
              }}
            >
              {gridCells}

              {/* VẼ BEACON UWB */}
              {systemMode === "uwb" &&
                mapData.beacon_location &&
                Object.entries(mapData.beacon_location).map(([id, pos]) => (
                  <div
                    key={`beacon-${id}`}
                    className="beacon-dot-wrapper"
                    style={{
                      left: `${pos.x * CELL_SIZE}px`,
                      top: `${(rows - pos.y) * CELL_SIZE}px`,
                    }}
                  >
                    <div className="beacon-dot"></div>
                    <div className="beacon-number-label">{id}</div>
                  </div>
                ))}

              {/* VẼ NGỌN LỬA */}
              {sessionFires.map((fire, idx) => {
                if (fire.status === "waiting") return null;
                const requiredTime = 3;
                const progressPercent = (fire.progress / requiredTime) * 100;

                let icon;
                // prettier-ignore
                if (fire.is_spreading) {
                  icon =
                    fire.level === 1 ? (
                      <img
                        src={fireSpread1Icon}
                        alt="Spreading Fire Level 1"
                        style={{ width: "1.2em", height: "1.2em",display: "block",}}
                      />
                    ) : fire.level === 2 ? (
                      <img
                        src={fireSpread2Icon}
                        alt="Spreading Fire Level 2"
                        style={{ width: "1.2em", height: "1.2em", display: "block",}}
                      />
                    ) : fire.level === 3 ? (
                      <img
                        src={fireSpread3Icon}
                        alt="Spreading Fire Level 3"
                        style={{ width: "1.2em", height: "1.2em", display: "block",}}
                      />
                    ) : fire.level === 4 ? (
                      <img
                        src={fireSpread3Icon}
                        alt="Spreading Fire Level 4"
                        style={{ width: "1.2em", height: "1.2em", display: "block",}}
                      />
                    ) : (
                      <img
                        src={fireSpread3Icon}
                        alt="Spreading Fire Level 5"
                        style={{ width: "1.2em", height: "1.2em", display: "block",}}
                      />
                    );
                }
                // prettier-ignore
                else {
                  icon =
                    fire.level === 1 ? (
                      <img
                        src={fire1Icon}
                        alt="Fire Level 1"
                        style={{width: "1.2em", height: "1.2em", display: "block",}}
                      />
                    ) : fire.level === 2 ? (
                      <img
                        src={fire2Icon}
                        alt="Fire Level 2"
                        style={{ width: "1.2em", height: "1.2em", display: "block",}}
                      />
                    ) : (
                      <img
                        src={fire3Icon}
                        alt="Fire Level 3"
                        style={{ width: "1.2em", height: "1.2em", display: "block",}}
                      />
                    );
                }

                const cssClass = fire.is_spreading
                  ? "sim-fire-icon fire-spreading"
                  : "sim-fire-icon";

                return (
                  <div
                    key={`fire-${idx}`}
                    className="sim-fire-wrapper"
                    style={{
                      left: `${fire.coord_x * CELL_SIZE}px`,
                      top: `${(rows - fire.coord_y) * CELL_SIZE}px`,
                    }}
                  >
                    {fire.status === "burning" ? (
                      <>
                        {/* ICON RENDER THEO LEVEL VÀ SPREAD */}
                        <div className={`${cssClass} fire-lv${fire.level}`}>
                          {icon}
                        </div>
                        {progressPercent > 0 && (
                          <div className="sim-progress-bar">
                            <div
                              className="sim-progress-fill"
                              style={{ width: `${progressPercent}%` }}
                            ></div>
                          </div>
                        )}
                      </>
                    ) : (
                      <div className="sim-extinguished"></div>
                    )}
                  </div>
                );
              })}
              <div className="radar-clipping-layer">
                {/* VẼ ĐƯỜNG QUỸ ĐẠO BẰNG SVG */}
                {showTrajectory && (
                  <svg
                    style={{
                      position: "absolute",
                      top: 0,
                      left: 0,
                      width: "100%",
                      height: "100%",
                      pointerEvents: "none" /* Chống click nhầm vào nét vẽ */,
                      zIndex: 1,
                    }}
                  >
                    {Object.entries(trajectoryRef.current).map(
                      ([tagId, points], idx) => {
                        if (points.length < 2) return null;

                        const color = TAG_COLORS[idx % TAG_COLORS.length];
                        const pointsString = points
                          .map((p) => {
                            const cx =
                              Math.max(0, Math.min(cols, p.x)) * CELL_SIZE;
                            const cy =
                              (rows - Math.max(0, Math.min(rows, p.y))) *
                              CELL_SIZE;
                            return `${cx},${cy}`;
                          })
                          .join(" ");

                        return (
                          <polyline
                            key={`traj-${tagId}`}
                            points={pointsString}
                            fill="none"
                            stroke={color}
                            strokeWidth="1.5"
                            opacity="0.5"
                            strokeLinecap="round"
                            strokeLinejoin="round"
                          />
                        );
                      },
                    )}
                  </svg>
                )}
                {/* VẼ TAG DI CHUYỂN, GÓC YAW */}
                {Object.entries(locations).map(([tagId, loc], idx) => {
                  const hexColor = TAG_COLORS[idx % TAG_COLORS.length];
                  if (loc.x === undefined || loc.y === undefined) return null;

                  // Giới hạn tọa độ của tag trong phạm vi map
                  const clampedX = Math.max(0, Math.min(cols, loc.x));
                  const clampedY = Math.max(0, Math.min(rows, loc.y));

                  const valve = loc.valve_per !== undefined ? loc.valve_per : 0;
                  const spray =
                    loc.spray_per !== undefined ? loc.spray_per : 100;

                  const angle = 15 + (spray / 100) * (60 - 15);
                  const radiusM = 2 - (spray / 100) * (2 - 1);
                  const cellLengthMeters = Math.sqrt(
                    mapData.area_of_one_unit || 1,
                  );
                  const radiusInCells = radiusM / cellLengthMeters;
                  const diameterPx = radiusInCells * CELL_SIZE * 2;
                  const startAngle = 360 - angle / 2;

                  // Đổi hex sang rgba để chỉnh opacity động
                  const r = parseInt(hexColor.slice(1, 3), 16);
                  const g = parseInt(hexColor.slice(3, 5), 16);
                  const b = parseInt(hexColor.slice(5, 7), 16);

                  // Tính toán độ mờ (Alpha) dựa trên Valve. (Valve 0 -> alpha 0. Valve 100 -> alpha 0.7)
                  const alpha = (valve / 100) * 0.7;
                  // Nối lại thành chuỗi màu RGBA hoàn chỉnh
                  const rgbaColor = `rgba(${r}, ${g}, ${b}, ${alpha})`;
                  // Hiệu chỉnh góc yaw theo North Offset của map
                  const rawYaw = loc.yaw || 0;
                  const northOffset = mapData.north_offset || 0;
                  const realYaw = rawYaw - northOffset;

                  return (
                    <div
                      key={tagId}
                      className="radar-dot"
                      style={{
                        left: `${clampedX * CELL_SIZE}px`,
                        top: `${(rows - clampedY) * CELL_SIZE}px`,
                      }}
                    >
                      <div
                        className="yaw-cone"
                        style={{
                          width: `${diameterPx}px`,
                          height: `${diameterPx}px`,
                          transform: `translate(-50%, -50%) rotate(${realYaw}deg)`,
                          background: `conic-gradient(from ${startAngle}deg, ${rgbaColor} 0deg, ${rgbaColor} ${angle}deg, transparent ${angle}deg)`,
                        }}
                      ></div>

                      <div
                        className="tag-base"
                        style={{ boxShadow: `0 0 8px ${hexColor}` }}
                      >
                        <div
                          className="tag-core"
                          style={{ backgroundColor: hexColor }}
                        ></div>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* POPUP ĐẾM NGƯỢC */}
      {selectedScenarioId !== "free" && trainingState === "idle" && (
        <div className="rm-start-overlay">
          {countdown === null ? (
            <div
              style={{
                display: "flex",
                flexDirection: "column",
                alignItems: "center",
              }}
            >
              <button
                className="rm-huge-play-btn"
                onClick={handleInitiateTraining}
              >
                <Play
                  size={54}
                  fill="white"
                  color="white"
                  style={{ marginLeft: 8 }}
                />
              </button>
              <div
                className="rm-cancel-hint"
                onClick={() => setSelectedScenarioId("free")}
              >
                Tap here to cancel
              </div>
            </div>
          ) : (
            <div className="rm-countdown-text">{countdown}</div>
          )}
        </div>
      )}

      {/* POPUP CẢNH BÁO LỬA LAN */}
      {spreadWarning && (
        <div className="spread-warning-banner">
          <div className="swb-icon">
            <AlertTriangle
              size={44}
              fill="#ED5B1D"
              color="white"
              strokeWidth={2}
            />
          </div>
          <div className="swb-content">
            <div className="swb-title">WARNING!</div>
            <div className="swb-desc">
              The fire is spreading. Extinguish it immediately!
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default RealtimeMonitor;

// Góc yaw có cần north offset để vẽ chính xác không, như trong file tôi gửi là đang mặc định là góc north offset hướng lên đúng không. Bây giờ sửa code để có thể config được góc northoffset cho nó tính theo 1 góc bất kỳ được không. MCU cần góc north offset để làm gì.
