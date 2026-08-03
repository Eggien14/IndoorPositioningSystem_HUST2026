import axios from "axios";
import React, { useState } from "react";
import {
  Loader2,
  CheckCircle,
  AlertTriangle,
  ArrowRight,
  Database,
  X,
} from "lucide-react";
import "../assets/css/CollectData.css";
import { useMessage } from "./MessageModal";

const CELL_SIZE = 38;

function CollectData({ mapData }) {
  const [selectedCell, setSelectedCell] = useState(null);
  const [collectedCells, setCollectedCells] = useState(new Set());
  const [samples, setSamples] = useState(50);
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState("");

  const [submitStatus, setSubmitStatus] = useState("idle");
  const [submitMessage, setSubmitMessage] = useState("");
  const [trainModelStatus, setTrainModelStatus] = useState("idle");
  const [trainModelMessage, setTrainModelMessage] = useState("");
  const [progress, setProgress] = useState(0);

  const rows = mapData.rows || 10;
  const cols = mapData.cols || 10;
  const blocked = new Set(mapData.blocked_cells || []);
  const routers = new Set(mapData.router_location || []);

  const { showAlert, showConfirm } = useMessage();

  React.useEffect(() => {
    const ws = new WebSocket("ws://localhost:8000/ws/realtime_location");
    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.type === "collect_progress") {
          setProgress(data.collected);
        }
      } catch (err) {}
    };
    return () => ws.close();
  }, []);

  const handleCellClick = (r, c) => {
    const key = `${(c + 0.5).toFixed(1)}:${(rows - 1 - r + 0.5).toFixed(1)}`;
    if (blocked.has(key)) {
      showAlert("Warning", "Cannot collect data on a blocked cell!");
      return;
    }
    if (collectedCells.has(key)) {
      showConfirm(
        "Are you sure?",
        "This cell has already been data-collected. Are you sure you want to re-collect data?",
        () => {
          setSelectedCell({
            r,
            c,
            x: (0.5 + c).toFixed(1),
            y: (rows - 1 - r + 0.5).toFixed(1),
          });
          setMessage("");
        },
      );
      return;
    }
    setSelectedCell({
      r,
      c,
      x: (0.5 + c).toFixed(1),
      y: (rows - 1 - r + 0.5).toFixed(1),
    });
    setMessage("");
  };

  const handleCollectData = async () => {
    setLoading(true);
    setMessage("");
    setProgress(0);
    try {
      const payload = {
        map_info_id: mapData.map_info_id,
        coord_x: Number(selectedCell.x),
        coord_y: Number(selectedCell.y),
        samples: Number(samples),
      };
      const res = await axios.post(
        "http://localhost:8000/collect_data",
        payload,
      );

      const cellKey = `${selectedCell.c}:${selectedCell.r}`;
      setCollectedCells((prev) => new Set(prev).add(cellKey));

      setMessage(res.data.message);
      setTimeout(() => {
        setSelectedCell(null);
        setLoading(false);
        setProgress(0);
      }, 2000);
    } catch (err) {
      showAlert("Error", "Failed to collect data.", "error");
      setLoading(false);
    }
  };

  const handleSubmit = async () => {
    setSubmitStatus("processing");
    setSubmitMessage("Processing RSSI data...");
    try {
      const res = await axios.post(
        `http://localhost:8000/preprocess_map/${mapData.map_info_id}`,
      );
      setSubmitStatus("success");
      setSubmitMessage(res.data.message);
    } catch (err) {
      console.error(err);
      setSubmitStatus("error");
      setSubmitMessage("Failed to generate CSV data. Check Backend log.");
    }
    setTimeout(() => {
      setSubmitMessage("");
      setSubmitStatus("idle");
    }, 4000);
  };

  const handleTrainModel = async () => {
    setTrainModelStatus("processing");
    setTrainModelMessage(
      "Model AI is learning... This may take a few minutes.",
    );
    try {
      const res = await axios.post(
        `http://localhost:8000/train_model/${mapData.map_info_id}`,
      );
      setTrainModelStatus("success");
      setTrainModelMessage(res.data.message);
    } catch (err) {
      console.error(err);
      setTrainModelStatus("error");
      setTrainModelMessage("Training failed. Check log terminal.");
    }
    setTimeout(() => {
      setTrainModelMessage("");
      setTrainModelStatus("idle");
    }, 5000);
  };

  const renderSubmitNotification = () => {
    if (!submitMessage) return null;
    let containerClass = "cd-notification-container";
    let Icon = null;
    if (submitStatus === "processing") {
      containerClass += " cd-notification-processing";
      Icon = <Loader2 size={18} className="spin" />;
    } else if (submitStatus === "success") {
      containerClass += " cd-notification-success";
      Icon = <CheckCircle size={18} />;
    } else if (submitStatus === "error") {
      containerClass += " cd-notification-error";
      Icon = <AlertTriangle size={18} />;
    }
    return (
      <div className={containerClass}>
        {Icon}
        <span>{submitMessage}</span>
      </div>
    );
  };

  const renderTrainModelNotification = () => {
    if (!trainModelMessage) return null;
    let containerClass = "cd-notification-container";
    let Icon = null;
    if (trainModelStatus === "processing") {
      containerClass += " cd-notification-processing";
      Icon = <Loader2 size={18} className="spin" />;
    } else if (trainModelStatus === "success") {
      containerClass += " cd-notification-success";
      Icon = <CheckCircle size={18} />;
    } else if (trainModelStatus === "error") {
      containerClass += " cd-notification-error";
      Icon = <AlertTriangle size={18} />;
    }
    return (
      <div className={containerClass}>
        {Icon}
        <span>{trainModelMessage}</span>
      </div>
    );
  };

  const renderSubmitButton = () => {
    const isProcessing = submitStatus === "processing";
    return (
      <button
        className="btn-run-model"
        onClick={handleSubmit}
        disabled={isProcessing}
      >
        {isProcessing ? (
          <Loader2 size={18} className="spin" />
        ) : (
          <ArrowRight size={18} />
        )}
        {isProcessing ? "Processing..." : "Submit"}
      </button>
    );
  };

  const renderTrainModelButton = () => {
    const isProcessing = trainModelStatus === "processing";
    return (
      <button
        className="btn-run-model"
        onClick={handleTrainModel}
        disabled={
          trainModelStatus === "processing" || submitStatus === "processing"
        }
      >
        {trainModelStatus === "processing" ? (
          <Loader2 size={18} className="spin" />
        ) : (
          <ArrowRight size={18} />
        )}
        {trainModelStatus === "processing" ? "Training..." : "Train Model"}
      </button>
    );
  };

  const cells = [];
  for (let r = 0; r < rows; r++) {
    for (let c = 0; c < cols; c++) {
      const coordX = (c + 0.5).toFixed(1);
      const coordY = (rows - 1 - r + 0.5).toFixed(1);

      const key = `${coordX}:${coordY}`;
      const isBlocked = blocked.has(key);
      const hasRouter = routers.has(key);
      const isCollected = collectedCells.has(key);

      cells.push(
        <button
          key={key}
          type="button"
          className={`map-cell ${isBlocked ? "blocked" : ""} ${hasRouter ? "router-cell" : ""} ${isCollected ? "collected" : ""}`}
          onClick={() => handleCellClick(r, c)}
          title={
            hasRouter
              ? `Router (${coordX}, ${coordY})`
              : isBlocked
                ? `Blocked (${coordX}, ${coordY})`
                : `Blank (${coordX}, ${coordY})`
          }
        >
          {hasRouter && <span className="router-icon">📡</span>}
        </button>,
      );
    }
  }

  return (
    <div className="rm-container">
      <div className="rm-header">
        <div className="rm-title-area">
          <h2 className="rm-title-text">
            Collect Data Map #{mapData.map_info_id}
          </h2>
        </div>

        <div className="rm-action-area">
          {renderSubmitNotification()}
          {renderTrainModelNotification()}
          {renderSubmitButton()}
          {renderTrainModelButton()}
        </div>
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

        {/* LƯỚI BẢN ĐỒ */}
        <div
          className="map-grid"
          style={{
            gridTemplateColumns: `repeat(${cols}, ${CELL_SIZE}px)`,
            gridTemplateRows: `repeat(${rows}, ${CELL_SIZE}px)`,
          }}
        >
          {cells}
        </div>
      </div>
      {selectedCell && (
        <div
          className="modal-overlay"
          onClick={() => {
            if (!loading) setSelectedCell(null);
          }}
        >
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <button
              className="btn-close-modal"
              onClick={() => {
                if (!loading) setSelectedCell(null);
              }}
            >
              <X size={24} />
            </button>
            <div className="modal-icon">
              <Database size={24} />
            </div>
            <h2 className="modal-title">Collect RSSI Data</h2>
            <p className="modal-subtitle">
              Coordinate:{" "}
              <strong>
                X: {selectedCell.x}, Y: {selectedCell.y}
              </strong>
            </p>
            <div className="label-form">
              <label className="label-title">Number of samples:</label>
              <input
                className="modal-input"
                type="number"
                value={samples}
                onChange={(e) => setSamples(e.target.value)}
              />
            </div>
            {message && (
              <div className="success-message">
                <CheckCircle size={18} /> {message}
              </div>
            )}
            <button
              className="btn-modal-submit"
              onClick={handleCollectData}
              disabled={loading || message !== ""}
            >
              {loading
                ? `Collecting... (${progress}/${samples})`
                : message
                  ? "Done!"
                  : "Start"}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

export default CollectData;
