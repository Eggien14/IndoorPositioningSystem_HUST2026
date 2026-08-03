import React, { createContext, useState, useContext } from "react";
import { AlertTriangle, X, Check } from "lucide-react";
import "../assets/css/MessageModal.css";

const MessageContext = createContext();

// Export Custom Hook để các file khác gọi: const { showAlert, showConfirm } = useMessage();
export const useMessage = () => useContext(MessageContext);

// Provider bọc ngoài cùng ứng dụng
export const MessageProvider = ({ children }) => {
  const [modalState, setModalState] = useState({
    isOpen: false,
    type: "alert",
    title: "",
    message: "",
    variant: "warning",
    onConfirm: null,
    onCancel: null,
  });

  // Hàm hiển thị Alert
  const showAlert = (title, message, variant = "warning") => {
    setModalState({
      isOpen: true,
      type: "alert",
      title,
      message,
      variant,
      onConfirm: () => setModalState({ ...modalState, isOpen: false }),
      onCancel: null,
    });
  };

  // Hàm hiển thị Confirm
  const showConfirm = (
    title,
    message,
    onConfirmCallback,
    onCancelCallback = null,
    variant = "warning",
  ) => {
    setModalState({
      isOpen: true,
      type: "confirm",
      title,
      message,
      variant,
      onConfirm: () => {
        setModalState({ ...modalState, isOpen: false });
        if (onConfirmCallback) onConfirmCallback();
      },
      onCancel: () => {
        setModalState({ ...modalState, isOpen: false });
        if (onCancelCallback) onCancelCallback();
      },
    });
  };

  const closeModal = () => {
    setModalState((prev) => ({ ...prev, isOpen: false }));
  };

  return (
    <MessageContext.Provider value={{ showAlert, showConfirm }}>
      {children}

      {/* KHUNG GIAO DIỆN HIỂN THỊ POPUP */}
      {modalState.isOpen && (
        <div className="msg-modal-overlay" onClick={closeModal}>
          <div
            className="msg-modal-content"
            onClick={(e) => e.stopPropagation()}
          >
            <button className="msg-modal-close" onClick={closeModal}>
              <X size={20} />
            </button>

            <div className={`msg-modal-icon ${modalState.variant}`}>
              {modalState.variant === "success" ? (
                <Check size={32} color="white" strokeWidth={3} />
              ) : modalState.variant === "error" ? (
                <X size={28} color="white" />
              ) : (
                <AlertTriangle size={28} color="white" />
              )}
            </div>

            <h2 className="msg-modal-title">{modalState.title}</h2>
            <p className="msg-modal-desc">{modalState.message}</p>

            <div className="msg-modal-actions">
              {modalState.type === "confirm" && (
                <button
                  className="btn-msg-cancel"
                  onClick={modalState.onCancel || closeModal}
                >
                  Cancel
                </button>
              )}
              <button
                className="btn-msg-confirm"
                onClick={modalState.onConfirm}
              >
                {modalState.type === "confirm" ? "Confirm" : "OK"}
              </button>
            </div>
          </div>
        </div>
      )}
    </MessageContext.Provider>
  );
};
