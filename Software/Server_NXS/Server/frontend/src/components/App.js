import React, { useEffect, useState, useCallback } from "react";
import axios from "axios";
import "../assets/css/App.css";
import { useMessage } from "./MessageModal";
import MapEditor from "./MapEditor";
import CollectData from "./CollectData";
import RealtimeMonitor from "./RealtimeMonitor";
import LandingPage from "./LandingPage";
import Scenarios from "./Scenarios";
import {
  House,
  RotateCw,
  Plus,
  Undo2,
  SquarePen,
  DatabaseZap,
  Trash2,
  Video,
  AlertTriangle,
  CheckCircle2,
  Flame,
} from "lucide-react";

const api = axios.create({
  baseURL: "http://localhost:8000",
});

function App() {
  const [isLoggedIn, setIsLoggedIn] = useState(false);
  const [systemMode, setSystemMode] = useState("selection"); // "selection", "fingerprint", "uwb"
  const [maps, setMaps] = useState([]);
  const [view, setView] = useState("maps");
  const [selectedMap, setSelectedMap] = useState(null);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const { showConfirm } = useMessage();

  // Hàm gọi API tự động đổi endpoint dựa trên chế độ
  const fetchMaps = useCallback(async (currentMode) => {
    if (currentMode === "selection") return;
    setLoading(true);
    try {
      const endpoint =
        currentMode === "fingerprint" ? "/rssi_maps" : "/uwb_maps";
      const res = await api.get(endpoint);
      setMaps(res.data);
      setError("");
    } catch (err) {
      setError(`Failed to fetch ${currentMode.toUpperCase()} maps`);
    }
    setLoading(false);
  }, []);

  useEffect(() => {
    fetchMaps(systemMode);
  }, [systemMode, fetchMaps]);

  useEffect(() => {
    if (message) {
      const timer = setTimeout(() => setMessage(""), 5000);
      return () => clearTimeout(timer);
    }
  }, [message]);

  useEffect(() => {
    if (error) {
      const timer = setTimeout(() => setError(""), 5000);
      return () => clearTimeout(timer);
    }
  }, [error]);

  const handleEdit = (map) => {
    setSelectedMap(map);
    setView("map");
    setMessage("");
    setError("");
  };

  const handleDelete = async (id) => {
    showConfirm(
      "Are you sure delete this map?",
      "This action can't be undone. Please confirm if you want to proceed.",
      async () => {
        setLoading(true);
        setMessage("");
        setError("");

        try {
          const endpoint =
            systemMode === "fingerprint" ? "/rssi_maps" : "/uwb_maps";
          await api.delete(`${endpoint}/${id}`);
          setMessage("Map deleted successfully");
          fetchMaps(systemMode);
        } catch (err) {
          setError(err.response?.data?.detail || "Delete failed");
        }
        setLoading(false);
      },
    );
  };

  const onMapSaved = (savedMap) => {
    setMessage("Map saved successfully");
    setSelectedMap(null);
    setView("maps");
    fetchMaps(systemMode);
  };

  // Nếu chưa đăng nhập render LandingPage
  if (!isLoggedIn || systemMode === "selection") {
    return (
      <LandingPage
        isLoggedIn={isLoggedIn}
        onLoginSuccess={() => {
          setIsLoggedIn(true);
        }}
        onSelectMode={(mode) => {
          setSystemMode(mode);
          setView("maps");
        }}
      />
    );
  }

  return (
    <div className="app-bg">
      {/* HIỆU ỨNG BACKGROUND */}
      <div className="app-visuals">
        <div className="blob blob-1"></div>
        <div className="blob blob-2"></div>
        <div className="blob blob-3"></div>
        <div className="blob blob-4"></div>
        <div className="blob blob-5"></div>
      </div>

      {/* TOPBAR */}
      <header className="topbar">
        <div className="brand">
          <span className="brand-badge">🙂</span>{" "}
          <h1>
            <div>
              {systemMode === "selection"
                ? "iPAC Lab"
                : systemMode === "fingerprint"
                  ? "RSSI Fingerprinting"
                  : "UWB Trilateration"}
            </div>
          </h1>
        </div>

        <div className="top-actions">
          {systemMode !== "selection" && (
            <button
              className="btn btn-secondary"
              onClick={() => {
                setSystemMode("selection");
                setView("maps");
                setMaps([]);
              }}
              title="Home"
            >
              <House size={20} />
            </button>
          )}

          {systemMode !== "selection" && view === "maps" && (
            <button
              className="btn btn-light"
              onClick={() => fetchMaps(systemMode)}
              disabled={loading}
              title="Refresh"
            >
              <RotateCw size={20} />
            </button>
          )}

          {systemMode !== "selection" && (
            <button
              className="btn btn-dark"
              onClick={() => {
                setSelectedMap(null);
                setView(view === "maps" ? "map" : "maps");
              }}
            >
              {view === "maps" ? <Plus size={20} /> : <Undo2 size={20} />}
            </button>
          )}
        </div>
      </header>

      <div className="container">
        {/* MÀN HÌNH 1: DANH SÁCH MAPS */}
        {systemMode !== "selection" && view === "maps" && (
          <>
            <div className="stats">
              <div className="chip">Total maps: {maps.length}</div>
            </div>

            <div className="content-grid">
              <div className="card">
                <h2>Maps</h2>
                {loading ? (
                  <div>Loading...</div>
                ) : (
                  <div className="scroll-x">
                    <table className="map-table">
                      <thead>
                        <tr>
                          <th>ID</th>
                          <th>Total units</th>
                          <th>Area/unit</th>
                          <th>North Offset</th>

                          {systemMode === "fingerprint" ? (
                            <>
                              <th>Router number</th>
                              <th>Router location</th>
                            </>
                          ) : (
                            <>
                              <th>Beacon number</th>
                              <th>Beacon location</th>
                            </>
                          )}
                          <th>Walkable</th>
                          <th>Actions</th>
                        </tr>
                      </thead>
                      <tbody>
                        {maps.map((map) => (
                          <tr key={map.map_info_id}>
                            <td>{map.map_info_id}</td>
                            <td>{map.total_units}</td>
                            <td>{map.area_of_one_unit}</td>
                            <td>{map.north_offset}</td>
                            {systemMode === "fingerprint" ? (
                              <>
                                <td>{map.router_number}</td>
                                <td>
                                  {Array.isArray(map.router_location)
                                    ? map.router_location
                                        .map((loc) => {
                                          const [x, y] = loc.split(":");
                                          return `${x}:${y}`;
                                        })
                                        .join(", ")
                                    : map.router_location}
                                </td>
                              </>
                            ) : (
                              <>
                                <td>{map.beacon_number || 0}</td>
                                <td>
                                  {map.beacon_location &&
                                  typeof map.beacon_location === "object"
                                    ? Object.entries(map.beacon_location)
                                        .map(([id, pos]) => `${pos.x}:${pos.y}`)
                                        .join(", ")
                                    : ""}
                                </td>
                              </>
                            )}

                            <td>{map.walkable_area}</td>
                            <td>
                              {/* CÁC NÚT ACTION */}
                              <div className="row-actions">
                                <button
                                  className="btn btn-edit"
                                  onClick={() => handleEdit(map)}
                                  title="Edit"
                                >
                                  <SquarePen size={20} />
                                </button>
                                {systemMode === "fingerprint" && (
                                  <button
                                    className="btn btn-colect"
                                    onClick={() => {
                                      setSelectedMap(map);
                                      setView("collect");
                                    }}
                                    title="Colect Data"
                                  >
                                    <DatabaseZap size={20} />
                                  </button>
                                )}
                                <button
                                  className="btn btn-training-scenario"
                                  onClick={() => {
                                    setSelectedMap(map);
                                    setView("scenarios");
                                  }}
                                  title="Training Scenarios"
                                >
                                  <Flame size={20} />
                                </button>
                                <button
                                  className="btn btn-monitor"
                                  onClick={() => {
                                    setSelectedMap(map);
                                    setView("monitor");
                                  }}
                                  title="Monitor"
                                >
                                  <Video size={20} />
                                </button>
                                <button
                                  className="btn btn-delete"
                                  onClick={() => handleDelete(map.map_info_id)}
                                  title="Delete"
                                >
                                  <Trash2 size={20} />
                                </button>
                              </div>
                            </td>
                          </tr>
                        ))}

                        {maps.length === 0 && (
                          <tr>
                            <td colSpan={8}>No maps found.</td>
                          </tr>
                        )}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
            </div>

            {message && (
              <div className="success-msg">
                <CheckCircle2 size={18} /> {message}
              </div>
            )}
            {error && (
              <div className="error-msg">
                <AlertTriangle size={18} /> {error}
              </div>
            )}
          </>
        )}

        {/* CÁC MÀN HÌNH KHI CLICK VÀO CÁC NÚT ACTION*/}
        {view === "map" && (
          <MapEditor
            mapToEdit={selectedMap}
            systemMode={systemMode}
            onSaved={onMapSaved}
            onCancel={() => {
              setSelectedMap(null);
              setView("maps");
            }}
          />
        )}
        {view === "collect" && systemMode === "fingerprint" && (
          <CollectData
            mapData={selectedMap}
            onBack={() => {
              setSelectedMap(null);
              setView("maps");
            }}
          />
        )}
        {view === "scenarios" && (
          <Scenarios
            mapData={selectedMap}
            systemMode={systemMode}
            onBack={() => {
              setSelectedMap(null);
              setView("maps");
            }}
          />
        )}
        {view === "monitor" && (
          <RealtimeMonitor
            mapData={selectedMap}
            systemMode={systemMode}
            onBack={() => {
              setSelectedMap(null);
              setView("maps");
            }}
          />
        )}
      </div>
    </div>
  );
}

export default App;
