import React, { useState, useEffect } from "react";
import axios from "axios";
import { User, X } from "lucide-react";
import "../assets/css/LoginModal.css";
import { useMessage } from "./MessageModal";

const api = axios.create({
  baseURL: "http://localhost:8000",
});

function LoginModal({ isOpen, onClose, initialMode, onLoginSuccess }) {
  const [mode, setMode] = useState(initialMode); // 'login' hoặc 'register'
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");

  const { showAlert } = useMessage();
  useEffect(() => {
    if (isOpen) {
      setMode(initialMode);
      setUsername("");
      setPassword("");
    }
  }, [isOpen, initialMode]);

  if (!isOpen) return null;

  const handleSubmit = async (e) => {
    e.preventDefault();
    const endpoint = mode === "login" ? "/login" : "/register";
    try {
      const response = await api.post(endpoint, { username, password });

      if (mode === "login") {
        localStorage.setItem("userId", response.data.user_id);
        localStorage.setItem("username", response.data.username);
        onLoginSuccess();
        onClose();
      } else {
        showAlert(
          "Success!",
          "Registration successful! Please log in.",
          "success",
        );
        setMode("login");
        setPassword("");
      }
    } catch (err) {
      showAlert("Error", err.response?.data?.detail || "Failed", "error");
    }
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" onClick={(e) => e.stopPropagation()}>
        <button className="btn-close-modal" onClick={onClose}>
          <X size={24} />
        </button>

        <div className="modal-icon">
          <User size={24} />
        </div>

        <h2 className="modal-title">
          {mode === "login" ? "Welcome" : "Welcome"}
        </h2>
        <p className="modal-subtitle">
          {mode === "login"
            ? "Login to access your maps and settings"
            : "Create a new account"}
        </p>

        <form onSubmit={handleSubmit}>
          <input
            className="modal-input"
            type="text"
            placeholder="Username"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            required
          />
          <input
            className="modal-input"
            type="password"
            placeholder="Password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
          />
          <button className="btn-modal-submit" type="submit">
            {mode === "login" ? "Login" : "Sign Up"}
          </button>
        </form>

        <div className="modal-switch">
          {mode === "login" ? (
            <>
              Don't have an account?{" "}
              <span onClick={() => setMode("register")}>Sign up now</span>
            </>
          ) : (
            <>
              Already have an account?{" "}
              <span onClick={() => setMode("login")}>Login here</span>
            </>
          )}
        </div>
      </div>
    </div>
  );
}

export default LoginModal;
