import React, { useMemo, useState } from "react";
import axios from "axios";
import "../assets/css/MapEditor.css";
import { useMessage } from "./MessageModal";
import { Router, Box, Trash2, Plus, SquarePen } from "lucide-react";

const MAX_SIZE = 20;
const CELL_SIZE = 38;

function clampSize(value) {
  const n = Number(value);
  if (Number.isNaN(n)) return 1;
  return Math.min(Math.max(n, 1), MAX_SIZE);
}

function MapEditor({ mapToEdit, systemMode, onSaved, onCancel }) {
  const [rows, setRows] = useState(10);
  const [cols, setCols] = useState(10);
  const [blocked, setBlocked] = useState(() => new Set());
  const [routerLocations, setRouterLocations] = useState(() => new Set());
  const [uwbBeacons, setUwbBeacons] = useState({});
  const [editingBeacon, setEditingBeacon] = useState(null);
  const [gridKey, setGridKey] = useState(0);
  const [areaOfOneUnit, setAreaOfOneUnit] = useState(1);
  const [northOffset, setNorthOffset] = useState(90);
  const [mode, setMode] = useState("block");
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [dragStart, setDragStart] = useState(null);
  const [dragEnd, setDragEnd] = useState(null);
  const [dragAction, setDragAction] = useState(null);

  const { showAlert } = useMessage();

  React.useEffect(() => {
    if (mapToEdit) {
      setAreaOfOneUnit(mapToEdit.area_of_one_unit ?? 1);
      setNorthOffset(mapToEdit.north_offset ?? 90);
      if (mapToEdit.rows && mapToEdit.cols) {
        setRows(mapToEdit.rows);
        setCols(mapToEdit.cols);
      }

      if (mapToEdit.blocked_cells && Array.isArray(mapToEdit.blocked_cells)) {
        setBlocked(new Set(mapToEdit.blocked_cells));
      } else {
        setBlocked(new Set());
      }

      if (
        mapToEdit.router_location &&
        Array.isArray(mapToEdit.router_location)
      ) {
        setRouterLocations(new Set(mapToEdit.router_location));
      } else {
        setRouterLocations(new Set());
      }
      setUwbBeacons(mapToEdit.beacon_location || {});
      setMessage("");
      setError("");
    }
  }, [mapToEdit]);

  const totalCells = useMemo(() => rows * cols, [rows, cols]);

  const walkableCellIds = useMemo(() => {
    const ids = [];
    for (let r = 0; r < rows; r += 1) {
      for (let c = 0; c < cols; c += 1) {
        const key = `${(c + 0.5).toFixed(1)}:${(rows - 1 - r + 0.5).toFixed(1)}`;
        if (!blocked.has(key)) {
          ids.push(r * cols + c + 1);
        }
      }
    }
    return ids;
  }, [rows, cols, blocked]);

  const handleMouseDown = (r, c) => {
    const key = `${(c + 0.5).toFixed(1)}:${(rows - 1 - r + 0.5).toFixed(1)}`;

    if (mode === "block") {
      // Chế độ vẽ tường: Kéo thả
      const isCurrentlyBlocked = blocked.has(key);
      setDragAction(isCurrentlyBlocked ? "unblock" : "block");
      setDragStart({ r, c });
      setDragEnd({ r, c });
    } else if (mode === "router") {
      // Chế độ vẽ Router
      setRouterLocations((prev) => {
        const next = new Set(prev);
        if (next.has(key)) next.delete(key);
        else next.add(key);
        return next;
      });
    } else if (mode === "beacon" && systemMode === "uwb") {
      const nextNumber = Object.keys(uwbBeacons).length + 1;
      setEditingBeacon({
        id: nextNumber.toString(),
        x: (0.5 + c).toFixed(2),
        y: (rows - 1 - r + 0.5).toFixed(2),
        isNew: true,
      });
    }
  };

  const handleMouseEnter = (r, c) => {
    if (mode === "block" && dragStart) {
      setDragEnd({ r, c });
    }
  };

  const applySelection = () => {
    if (mode !== "block" || !dragStart || !dragEnd) return;

    const minR = Math.min(dragStart.r, dragEnd.r);
    const maxR = Math.max(dragStart.r, dragEnd.r);
    const minC = Math.min(dragStart.c, dragEnd.c);
    const maxC = Math.max(dragStart.c, dragEnd.c);

    setBlocked((prev) => {
      const next = new Set(prev);
      for (let r = minR; r <= maxR; r++) {
        for (let c = minC; c <= maxC; c++) {
          const key = `${(c + 0.5).toFixed(1)}:${(rows - 1 - r + 0.5).toFixed(1)}`;
          if (dragAction === "block") next.add(key);
          else next.delete(key);
        }
      }
      return next;
    });

    setDragStart(null);
    setDragEnd(null);
    setDragAction(null);
  };

  const resetBlocks = () => {
    setBlocked(new Set());
  };

  const resetRouters = () => {
    setRouterLocations(new Set());
  };

  const applySize = (event) => {
    event.preventDefault();
    const newRows = clampSize(rows);
    const newCols = clampSize(cols);
    setRows(newRows);
    setCols(newCols);
    resetBlocks();
    setGridKey((k) => k + 1);
    setMessage("");
    setError("");
  };

  // Hàm khi click vào bản đồ ở chế độ UWB
  const handleMapClick = (r, c) => {
    if (systemMode === "uwb" && mode === "beacon") {
      const nextNumber = Object.keys(uwbBeacons).length + 1;
      setEditingBeacon({
        id: nextNumber.toString(), // Tự động gợi ý id tiếp
        x: (0.5 + c).toFixed(2),
        y: (rows - 1 - r + 0.5).toFixed(2),
        isNew: true,
      });
    }
  };

  const saveBeacon = () => {
    if (!editingBeacon.id)
      return showAlert("Warning", "Please enter Beacon ID!");
    setUwbBeacons((prev) => {
      const next = { ...prev };

      // Chế độ edit Beacon
      if (
        editingBeacon.originalId &&
        editingBeacon.originalId !== editingBeacon.id
      ) {
        delete next[editingBeacon.originalId];
      }

      // Lưu thông tin mới
      next[editingBeacon.id] = {
        x: Number(editingBeacon.x),
        y: Number(editingBeacon.y),
      };
      return next;
    });
    setEditingBeacon(null);
  };

  const deleteBeacon = (id) => {
    const next = { ...uwbBeacons };
    delete next[id];
    setUwbBeacons(next);
  };

  const saveMap = async () => {
    setMessage("");
    setError("");

    try {
      const payload = {
        total_units: totalCells,
        area_of_one_unit: Number(areaOfOneUnit),
        north_offset: Number(northOffset),
        walkable_area: Number(walkableCellIds.length),
        cols: cols,
        rows: rows,
        blocked_cells: Array.from(blocked),
      };
      if (systemMode === "fingerprint") {
        payload.router_number = routerLocations.size;
        payload.router_location = Array.from(routerLocations);
      } else {
        payload.beacon_number = Object.keys(uwbBeacons).length; // Tự đếm số beacon
        payload.beacon_location = uwbBeacons;
      }

      const endpoint =
        systemMode === "fingerprint" ? "/rssi_maps" : "/uwb_maps";

      if (mapToEdit?.map_info_id) {
        const res = await axios.put(
          `${endpoint}/${mapToEdit.map_info_id}`,
          payload,
        );
        setMessage("Map updated successfully");
        onSaved?.(res.data);
      } else {
        const res = await axios.post(endpoint, payload);
        setMessage("Map created successfully");
        onSaved?.(res.data);
      }
    } catch (err) {
      const apiMsg =
        err.response?.data?.detail || err.response?.data || err.message;
      setError(apiMsg || "Failed to save map");
      console.error("Save map error", err);
    }
  };

  const xLabels = Array.from({ length: cols }, (_, i) => (0.5 + i).toFixed(1));
  const yLabels = Array.from({ length: rows }, (_, i) => (0.5 + i).toFixed(1));

  const cells = [];
  for (let r = 0; r < rows; r += 1) {
    for (let c = 0; c < cols; c += 1) {
      const coordX = (c + 0.5).toFixed(1);
      const coordY = (rows - 1 - r + 0.5).toFixed(1);

      const key = `${coordX}:${coordY}`;
      const actuallyBlocked = blocked.has(key);
      // Kiểm tra xem ô này có nằm trong vùng đang quét chuột không
      let inSelection = false;
      if (dragStart && dragEnd) {
        inSelection =
          r >= Math.min(dragStart.r, dragEnd.r) &&
          r <= Math.max(dragStart.r, dragEnd.r) &&
          c >= Math.min(dragStart.c, dragEnd.c) &&
          c <= Math.max(dragStart.c, dragEnd.c);
      }

      // Nếu đang quét qua, hiển thị trước kết quả (preview). Nếu không thì lấy trạng thái thật.
      const isBlocked = inSelection ? dragAction === "block" : actuallyBlocked;
      const hasRouter = routerLocations.has(key);

      cells.push(
        <button
          key={key}
          type="button"
          className={`map-cell ${isBlocked ? "blocked" : ""} ${hasRouter ? "router-cell" : ""} ${inSelection && mode === "block" ? "preview" : ""}`}
          onMouseDown={() => handleMouseDown(r, c)}
          onMouseEnter={() => handleMouseEnter(r, c)}
          onDragStart={(e) => e.preventDefault()}
          aria-label={`Cell ${coordX}, ${coordY}`}
          title={
            hasRouter
              ? `Router (${coordX}, ${coordY})`
              : isBlocked
                ? `Blocked (${coordX}, ${coordY})`
                : `Blank (${coordX}, ${coordY})`
          }
          data-coord={`${coordX}, ${coordY}`}
        >
          {hasRouter && <span className="router-icon">📡</span>}
        </button>,
      );
    }
  }

  return (
    <div className="map-editor">
      {(() => {
        return (
          <>
            <div className="map-sidebar">
              <h2 className="map-title">Map Editor</h2>

              {/* CÁC INPUT NHẬP Ở SIDEBAR */}
              <div className="sidebar-section">
                <label className="input-label">
                  Rows
                  <input
                    className="input-field"
                    type="number"
                    min={1}
                    max={MAX_SIZE}
                    value={rows}
                    onChange={(e) => setRows(clampSize(e.target.value))}
                  />
                </label>
                <label className="input-label">
                  Columns
                  <input
                    className="input-field"
                    type="number"
                    min={1}
                    max={MAX_SIZE}
                    value={cols}
                    onChange={(e) => setCols(clampSize(e.target.value))}
                  />
                </label>
                <label className="input-label">
                  Area/unit (m²)
                  <input
                    className="input-field"
                    type="number"
                    min={0}
                    step="0.1"
                    value={areaOfOneUnit}
                    onChange={(e) => setAreaOfOneUnit(e.target.value)}
                  />
                </label>
                <label className="input-label">
                  North Offset (°)
                  <input
                    className="input-field"
                    type="number"
                    min={0}
                    step="10"
                    value={northOffset}
                    onChange={(e) => setNorthOffset(e.target.value)}
                  />
                </label>
              </div>
              <div className="sidebar-actions">
                <button
                  className="btn-clear"
                  type="button"
                  onClick={resetBlocks}
                  disabled={blocked.size === 0}
                >
                  Clear blocks
                </button>
                {systemMode === "fingerprint" && (
                  <button
                    className="btn-clear"
                    type="button"
                    onClick={resetRouters}
                    disabled={routerLocations.size === 0}
                  >
                    Clear routers
                  </button>
                )}
              </div>
              <div className="sidebar-stats">
                <div className="stat-item">
                  <span>Total:</span> <b>{totalCells}</b>
                </div>
                <div className="stat-item">
                  <span>Walkable:</span> <b>{walkableCellIds.length}</b>
                </div>
                <div className="stat-item">
                  <span>
                    {systemMode === "fingerprint" ? "Routers:" : "Beacons:"}
                  </span>
                  <b>
                    {systemMode === "fingerprint"
                      ? routerLocations.size
                      : Object.keys(uwbBeacons).length}
                  </b>
                </div>
              </div>
              <div className="sidebar-footer">
                <button
                  className="btn-blue"
                  type="button"
                  onClick={(e) => {
                    applySize(e);
                    saveMap();
                  }}
                >
                  {mapToEdit ? "Update map" : "Create map"}
                </button>
                <button
                  className="btn-pink"
                  type="button"
                  onClick={() => onCancel?.()}
                >
                  Cancel
                </button>
              </div>
            </div>

            {/* KHU VỰC VẼ BẢN ĐỒ */}
            <div className="map-canvas">
              <div className="segmented-control">
                <button
                  type="button"
                  className={
                    mode === "block" ? "segment-btn active" : "segment-btn"
                  }
                  onClick={() => setMode("block")}
                >
                  <Box size={20} />
                </button>

                {systemMode === "fingerprint" ? (
                  <button
                    type="button"
                    className={
                      mode === "router" ? "segment-btn active" : "segment-btn"
                    }
                    onClick={() => setMode("router")}
                  >
                    <Router size={20} />
                  </button>
                ) : (
                  <button
                    type="button"
                    className={
                      mode === "beacon" ? "segment-btn active" : "segment-btn"
                    }
                    onClick={() => setMode("beacon")}
                  >
                    <Router size={20} />
                  </button>
                )}
              </div>

              <div
                className="map-grid-section"
                key={gridKey}
                style={{
                  "--map-cols": cols,
                  "--map-rows": rows,
                }}
              >
                <div className="corner-empty"></div>

                {/* TRỤC X TỌA ĐỘ TUYỆT ĐỐI VỚI BEACON VÀ TAG*/}
                <div
                  className="x-axis-container"
                  style={{
                    display: "grid",
                    gridTemplateColumns: `repeat(${cols}, ${CELL_SIZE}px)`,
                    gap: "0px",
                  }}
                >
                  {Array.from({ length: cols }, (_, i) => (
                    <div key={`x-${i}`} className="axis-label-box">
                      <span className="axis-text">{(0.5 + i).toFixed(1)}</span>
                      <div className="axis-tick-x"></div>
                    </div>
                  ))}
                </div>

                {/* TRỤC Y TỌA ĐỘ TUYỆT ĐỐI VỚI BEACON VÀ TAG */}
                <div
                  className="y-axis-container"
                  style={{
                    display: "grid",
                    gridTemplateRows: `repeat(${rows}, ${CELL_SIZE}px)`,
                    gap: "0px",
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
                  onMouseUp={applySelection}
                  onMouseLeave={applySelection}
                  style={{
                    gridTemplateColumns: `repeat(${cols}, ${CELL_SIZE}px)`,
                    gridTemplateRows: `repeat(${rows}, ${CELL_SIZE}px)`,
                    gap: "0px",
                  }}
                >
                  {cells}

                  {/* HIỂN THỊ BEACON UWB: Tọa độ tuyệt đối*/}
                  {systemMode === "uwb" &&
                    Object.entries(uwbBeacons).map(([id, pos]) => {
                      const leftPx = pos.x * CELL_SIZE;
                      const topPx = (rows - pos.y) * CELL_SIZE;

                      return (
                        <div
                          key={id}
                          className="beacon-dot-wrapper"
                          style={{
                            left: `${leftPx}px`,
                            top: `${topPx}px`,
                          }}
                        >
                          <div className="beacon-dot"></div>
                          <div className="beacon-number-label">{id}</div>
                        </div>
                      );
                    })}
                </div>
              </div>
            </div>
            {systemMode === "uwb" && (
              <div className="map-right-panel">
                <h2
                  className="map-title"
                  style={{ fontSize: "1.2rem", marginBottom: "15px" }}
                >
                  UWB Beacons
                </h2>
                <div className="beacon-list-container">
                  {Object.entries(uwbBeacons).map(([id, pos]) => (
                    <div key={id} className="beacon-item">
                      <div className="beacon-chip">#{id}</div>
                      <div className="beacon-info">
                        <span>
                          X: <b>{pos.x}</b>
                        </span>
                        <span>
                          Y: <b>{pos.y}</b>
                        </span>
                      </div>
                      <div className="beacon-actions">
                        <button
                          className="btn-edit-small"
                          onClick={() =>
                            setEditingBeacon({
                              id: id,
                              originalId: id,
                              x: pos.x,
                              y: pos.y,
                            })
                          }
                        >
                          <SquarePen size={14} />
                        </button>
                        <button
                          className="btn-delete-small"
                          onClick={() => deleteBeacon(id)}
                        >
                          <Trash2 size={14} />
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* POPUP CẤU HÌNH BEACON */}
            {editingBeacon && (
              <div className="modal-overlay">
                <div className="modal-content">
                  <div className="modal-title">Beacon Config</div>
                  <div className="modal-form">
                    <label className="input-label">
                      Beacon ID
                      <input
                        className="input-field"
                        value={editingBeacon.id}
                        onChange={(e) =>
                          setEditingBeacon({
                            ...editingBeacon,
                            id: e.target.value,
                          })
                        }
                        placeholder="eg: 0x01"
                      />
                    </label>
                    <div className="two-column-grid">
                      <label className="input-label">
                        X (m)
                        <input
                          className="input-field"
                          type="number"
                          step="0.01"
                          value={editingBeacon.x}
                          onChange={(e) =>
                            setEditingBeacon({
                              ...editingBeacon,
                              x: e.target.value,
                            })
                          }
                        />
                      </label>
                      <label className="input-label">
                        Y (m)
                        <input
                          className="input-field"
                          type="number"
                          step="0.01"
                          value={editingBeacon.y}
                          onChange={(e) =>
                            setEditingBeacon({
                              ...editingBeacon,
                              y: e.target.value,
                            })
                          }
                        />
                      </label>
                    </div>
                  </div>
                  <div className="btn-popup-actions">
                    <button className="btn-confirm" onClick={saveBeacon}>
                      Save
                    </button>
                    <button
                      className="btn-gray"
                      onClick={() => setEditingBeacon(null)}
                      style={{ flex: 1 }}
                    >
                      Cancel
                    </button>
                  </div>
                </div>
              </div>
            )}
          </>
        );
      })()}
    </div>
  );
}

export default MapEditor;
