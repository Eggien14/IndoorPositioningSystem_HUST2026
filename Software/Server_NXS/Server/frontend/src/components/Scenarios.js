import React, { useState, useEffect, useRef } from "react";
import axios from "axios";
import {
  ArrowLeft,
  Flame,
  FlameKindling,
  Plus,
  CheckCircle2,
  SquarePen,
  X,
  Save,
  Trash2,
} from "lucide-react";
import "../assets/css/Scenarios.css";
import { useMessage } from "./MessageModal";
import fire1Icon from "../assets/picture/fire_1.svg";
import fire2Icon from "../assets/picture/fire_2.svg";
import fire3Icon from "../assets/picture/fire_3.svg";
import fireSpread1Icon from "../assets/picture/flames_1.svg";
import fireSpread2Icon from "../assets/picture/flames_2.svg";
import fireSpread3Icon from "../assets/picture/flames_3.svg";

const CELL_SIZE = 38;

function Scenarios({ mapData, systemMode, onBack }) {
  const [scenarios, setScenarios] = useState([]);
  const [activeScenarioId, setActiveScenarioId] = useState("new"); // ID bài tập
  const [fireMode, setFireMode] = useState("normal"); // "normal" hoặc "spreading"
  const [scenarioName, setScenarioName] = useState("");
  const [fires, setFires] = useState([]);
  const [editingFire, setEditingFire] = useState(null);

  const [message, setMessage] = useState("");

  const rows = mapData.rows || 10;
  const cols = mapData.cols || 10;
  const blocked = new Set(mapData.blocked_cells || []);
  const routers = new Set(mapData.router_location || []);

  const { showAlert, showConfirm } = useMessage();

  // Flag chống gọi API 2 lần
  const hasFetched = useRef(false);

  const fetchScenarios = async () => {
    try {
      const res = await axios.get(
        `http://localhost:8000/scenarios/${systemMode}/${mapData.map_info_id}`,
      );
      setScenarios(res.data);
    } catch (err) {
      console.error("Failed to fetch scenarios", err);
    }
  };

  // Hàm chọn Scenario
  const handleSelectScenario = (e) => {
    const val = e.target.value;
    setActiveScenarioId(val);
    setMessage("");

    if (val === "new") {
      setScenarioName("");
      setFires([]);
    } else {
      const found = scenarios.find((s) => s.scenario_id === Number(val));
      if (found) {
        setScenarioName(found.scenario_name);
        setFires(found.fires);
      }
    }
  };

  // Click vào ô trên bản đồ
  const handleCellClick = (r, c) => {
    const coordX = (c + 0.5).toFixed(1);
    const coordY = (rows - 1 - r + 0.5).toFixed(1);
    const key = `${coordX}:${coordY}`;

    if (blocked.has(key)) {
      showAlert("Warning", "Cannot place fire on a blocked cell!");
      return;
    }

    const existingFireIndex = fires.findIndex(
      (f) => f.coord_x === Number(coordX) && f.coord_y === Number(coordY),
    );

    if (existingFireIndex >= 0) {
      return;
    } else {
      // Nếu chưa có, bật popup tạo mới (Mặc định level 1, delay 5s)
      setEditingFire({
        index: -1,
        coord_x: Number(coordX),
        coord_y: Number(coordY),
        level: 1,
        delay_time: 5,
        is_spreading: fireMode === "spreading",
      });
    }
  };

  // Hàm lấy icon ngọn lửa theo level
  // prettier-ignore
  const getFireIcon = (level, isSpreading) => {
    if (isSpreading) {
      if (level === 1) return <img src={fireSpread1Icon} alt="Spreading Level 1" className="fire-svg-icon" />;
      if (level === 2) return <img src={fireSpread2Icon} alt="Spreading Level 2" className="fire-svg-icon" />;
      if (level === 3) return <img src={fireSpread3Icon} alt="Spreading Level 3" className="fire-svg-icon" />;
      if (level === 4) return <img src={fireSpread3Icon} alt="Spreading Level 4" className="fire-svg-icon" />;
      return <img src={fireSpread3Icon} alt="Spreading Level 5" className="fire-svg-icon" />;
    }
    if (level === 1) return <img src={fire1Icon} alt="Fire Level 1" className="fire-svg-icon" />;
    if (level === 2) return <img src={fire2Icon} alt="Fire Level 2" className="fire-svg-icon" />;
    if (level === 3) return <img src={fire3Icon} alt="Fire Level 3" className="fire-svg-icon" />;
    if (level === 4) return <img src={fire3Icon} alt="Fire Level 4" className="fire-svg-icon" />;
    return <img src={fire3Icon} alt="Fire Level 5" className="fire-svg-icon" />;
  };

  const handleSaveFire = () => {
    const newFires = [...fires];
    if (editingFire.index >= 0) {
      newFires[editingFire.index] = editingFire; // Cập nhật
    } else {
      newFires.push(editingFire); // Thêm mới
    }
    setFires(newFires);
    setEditingFire(null);
  };

  const handleDeleteFire = (index) => {
    const newFires = fires.filter((_, i) => i !== index);
    setFires(newFires);
  };

  const handleSaveScenario = async () => {
    if (!scenarioName.trim()) return showAlert("Warning", "Please enter Scenario Name!");
    if (fires.length === 0)
      return showAlert("Warning", "Please place at least one fire on the map!");

    try {
      // MẸO UPDATE: Nếu đang sửa kịch bản cũ, xóa cái cũ trước khi tạo cái mới
      if (activeScenarioId !== "new") {
        await axios.delete(
          `http://localhost:8000/scenarios/${activeScenarioId}`,
        );
      }

      const payload = {
        map_info_id: mapData.map_info_id,
        map_type: systemMode,
        scenario_name: scenarioName,
        fires: fires,
      };

      await axios.post("http://localhost:8000/scenarios", payload);

      setMessage(
        activeScenarioId === "new"
          ? "Scenario saved successfully!"
          : "Scenario updated successfully!",
      );
      fetchScenarios();
      setActiveScenarioId("new"); // Trả về form trống
      setScenarioName("");
      setFires([]);

      setTimeout(() => setMessage(""), 3000);
    } catch (err) {
      showAlert("Error", "Failed to save scenario.", "error");
      console.error(err);
    }
  };

  const handleDeleteScenario = () => {
    showConfirm(
      "Are you sure delete this scenario?",
      "This action can't be undone. Please confirm if you want to proceed.",
      async () => {
        try {
          await axios.delete(
            `http://localhost:8000/scenarios/${activeScenarioId}`,
          );
          setMessage("Scenario deleted!");
          fetchScenarios();
          setActiveScenarioId("new");
          setScenarioName("");
          setFires([]);
          setTimeout(() => setMessage(""), 3000);
        } catch (err) {
          showAlert("Error", "Failed to delete scenario.", "error");
        }
      },
    );
  };

  // Render các ô vuông
  const gridCells = [];
  for (let r = 0; r < rows; r++) {
    for (let c = 0; c < cols; c++) {
      const coordX = (c + 0.5).toFixed(1);
      const coordY = (rows - 1 - r + 0.5).toFixed(1);
      const key = `${coordX}:${coordY}`;

      const isBlocked = blocked.has(key);
      const hasRouter = routers.has(key);
      const hasFire = fires.find(
        (f) => f.coord_x === Number(coordX) && f.coord_y === Number(coordY),
      );

      gridCells.push(
        <button
          key={key}
          type="button"
          className={`map-cell ${isBlocked ? "blocked" : ""} ${hasRouter ? "router-cell" : ""}`}
          onClick={() => handleCellClick(r, c)}
          title={`Cell (${coordX}, ${coordY})`}
        >
          {hasRouter && <span className="router-icon">📡</span>}
          {hasFire && (
            <span className={`fire-icon`}>
              {getFireIcon(hasFire.level, hasFire.is_spreading)}
            </span>
          )}
        </button>,
      );
    }
  }

  // Lấy danh sách các kịch bản của Map này từ Server
  useEffect(() => {
    if (hasFetched.current) return;
    hasFetched.current = true;

    fetchScenarios();
  }, [mapData.map_info_id, systemMode]);

  return (
    <div className="scenarios-container">
      <div className="scenarios-header">
        <div className="scenarios-title-group">
          <button className="btn btn-secondary" onClick={onBack}>
            <ArrowLeft size={20} />
          </button>
          <h2 className="rm-title-text">
            Training Scenario: Map #{mapData.map_info_id}
          </h2>
        </div>

        {message && (
          <div className="success-msg" style={{ margin: 0 }}>
            <CheckCircle2 size={18} /> {message}
          </div>
        )}
      </div>

      <div className="map-editor">
        {/* CỘT TRÁI: SIDEBAR CẤU HÌNH */}
        <div className="map-sidebar">
          {/* SELECT CHỌN SCENARIO */}
          <div className="scenario-selector-box">
            <select
              className="scenario-select"
              value={activeScenarioId}
              onChange={handleSelectScenario}
            >
              <option value="new">-- Create New Scenario --</option>
              {scenarios.map((sc) => (
                <option key={sc.scenario_id} value={sc.scenario_id}>
                  {sc.scenario_name}
                </option>
              ))}
            </select>
            <button
              className="btn-icon-square btn-icon-save"
              onClick={handleSaveScenario}
              title="Save Scenario"
            >
              <Save size={18} />
            </button>
            {activeScenarioId !== "new" && (
              <button
                className="btn-icon-square btn-icon-delete"
                onClick={handleDeleteScenario}
                title="Delete Scenario"
              >
                <Trash2 size={18} />
              </button>
            )}
          </div>
          {/* Cửa sổ Scenario Config */}
          <h2 className="map-title">Scenario Config</h2>

          <div className="scenario-name-wrapper">
            <label className="input-label">
              Scenario Name
              <input
                className="input-field-name"
                value={scenarioName}
                onChange={(e) => setScenarioName(e.target.value)}
                placeholder="e.g. D8-802"
              />
            </label>
          </div>

          <div className="inspector-panel">
            <div className="beacon-list-title">
              Fire Points (Total: {fires.length})
            </div>
            {fires.length === 0 && (
              <p className="inspector-hint">
                Click any blank cell to set fire.
              </p>
            )}

            <div className="beacon-list-container">
              {fires.map((f, i) => (
                <div key={i} className="fire-item">
                  <div className="fire-chip">
                    {getFireIcon(f.level, f.is_spreading)}
                  </div>

                  <div className="fire-info">
                    <div>
                      x : <strong>{f.coord_x}</strong> | y :{" "}
                      <strong>{f.coord_y}</strong>
                    </div>
                    <div>
                      Level: <strong>{f.level}</strong> | Start:{" "}
                      <strong>{f.delay_time}s</strong>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* CỘT PHẢI: LƯỚI BẢN ĐỒ */}
        <div className="map-canvas">
          <div className="segmented-control map-floating-segment">
            <button
              className={`segment-btn fire-mode ${fireMode === "normal" ? "active" : ""}`}
              onClick={() => setFireMode("normal")}
              title="Normal Fire Mode"
            >
              <img
                src={fire2Icon}
                alt="Normal Fire"
                className="segment-icon-img"
              />
            </button>
            <button
              className={`segment-btn spread-mode ${fireMode === "spreading" ? "active" : ""}`}
              onClick={() => setFireMode("spreading")}
              title="Spreading Fire Mode"
            >
              <img
                src={fireSpread3Icon}
                alt="Spreading Fire"
                className="segment-icon-img"
              />
            </button>
          </div>
          <div className="map-grid-section">
            <div className="corner-empty"></div>
            {/* TRỤC X */}
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
            {/* TRỤC Y */}
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
              {/* LƯỚI BẢN ĐỒ VÀ HOVER NGỌN LỬA */}
              {gridCells.map((cell) => {
                const c = Number(cell.key.split(":")[0]) - 0.5;
                const r = rows - 1 - (Number(cell.key.split(":")[1]) - 0.5);
                const isBlocked = blocked.has(cell.key);
                const hasRouter = routers.has(cell.key);
                const hasFire = fires.find(
                  (f) =>
                    f.coord_x === c + 0.5 && f.coord_y === rows - 1 - r + 0.5,
                );

                return (
                  <button
                    key={cell.key}
                    type="button"
                    className={`map-cell ${isBlocked ? "blocked" : ""} ${hasRouter ? "router-cell" : ""}`}
                    onClick={() => handleCellClick(r, c)}
                    title={`Cell (${cell.key.replace(":", ", ")})`}
                  >
                    {hasRouter && <span className="router-icon">📡</span>}

                    {/* KHỐI NGỌN LỬA VÀ 2 NÚT HOVER */}
                    {hasFire && (
                      <div className="fire-on-map-wrapper">
                        <span className="fire-icon">
                          {getFireIcon(hasFire.level, hasFire.is_spreading)}
                        </span>

                        <div className="fire-hover-actions">
                          <button
                            type="button"
                            className="fire-action-btn edit-btn"
                            onClick={(e) => {
                              e.stopPropagation(); // CỰC KỲ QUAN TRỌNG: Ngăn click lan xuống nền map
                              setEditingFire({
                                ...hasFire,
                                index: fires.indexOf(hasFire),
                              });
                            }}
                            title="Edit Fire"
                          >
                            <SquarePen size={14} />
                          </button>
                          <button
                            type="button"
                            className="fire-action-btn delete-btn"
                            onClick={(e) => {
                              e.stopPropagation();
                              handleDeleteFire(fires.indexOf(hasFire));
                            }}
                            title="Delete Fire"
                          >
                            <X size={14} />
                          </button>
                        </div>
                      </div>
                    )}
                  </button>
                );
              })}

              {/* VẼ BEACON VỚI MODE UWB */}
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
            </div>
          </div>
        </div>
      </div>

      {/* POPUP CẤU HÌNH THÔNG SỐ NGỌN LỬA */}
      {editingFire && (
        <div className="modal-overlay">
          <div className="modal-content">
            <h3 className="modal-header-title">Fire Configuration</h3>
            <p className="s-modal-subtitle">
              Coordinate: x={editingFire.coord_x}, y={editingFire.coord_y}
            </p>
            <div className="modal-form">
              <label className="input-label">
                Fire Level
                <select
                  className="input-field"
                  value={editingFire.level}
                  onChange={(e) =>
                    setEditingFire({
                      ...editingFire,
                      level: Number(e.target.value),
                    })
                  }
                >
                  <option value={1}>Level 1 (Small)</option>
                  <option value={2}>Level 2 (Medium)</option>
                  <option value={3}>Level 3 (Large)</option>
                  <option value={4}>Level 4 (Super Large)</option>
                  <option value={5}>Level 5 (Enormous)</option>
                </select>
              </label>

              <label className="input-label">
                Appearance Time (seconds)
                <input
                  type="number"
                  className="input-field"
                  min="0"
                  value={editingFire.delay_time}
                  onChange={(e) =>
                    setEditingFire({
                      ...editingFire,
                      delay_time: Number(e.target.value),
                    })
                  }
                />
              </label>
            </div>

            <div className="btn-popup-actions">
              <button className="btn-confirm" onClick={handleSaveFire}>
                Confirm
              </button>
              <button
                className="btn-gray"
                onClick={() => setEditingFire(null)}
                style={{ flex: 1 }}
              >
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default Scenarios;
