import React from "react";
import { Routes, Route, Navigate } from "react-router-dom";
import { useAuthStore } from "./store/authStore";

import Login from "./pages/Auth/Login";
import Register from "./pages/Auth/Register";
import ResetPassword from "./pages/Auth/ResetPassword";
import Dashboard from "./pages/Dashboard/Dashboard";
import Profile from "./pages/Profile/Profile";
import OwnProfile from "./pages/Profile/OwnProfile";
import Discover from "./pages/Discover/Discover";
import Room from "./pages/Room/Room";
import RoomList from "./pages/Room/RoomList";
import Messages from "./pages/Messages/Messages";

function PrivateRoute({ children }) {
  const token = useAuthStore((s) => s.accessToken);
  return token ? children : <Navigate to="/login" replace />;
}

function PublicRoute({ children }) {
  const token = useAuthStore((s) => s.accessToken);
  return token ? <Navigate to="/dashboard" replace /> : children;
}

export default function App() {
  return (
    <Routes>
      {/* Public */}
      <Route path="/login" element={<PublicRoute><Login /></PublicRoute>} />
      <Route path="/register" element={<PublicRoute><Register /></PublicRoute>} />
      <Route path="/reset-password" element={<ResetPassword />} />

      {/* Private */}
      <Route path="/dashboard" element={<PrivateRoute><Dashboard /></PrivateRoute>} />
      <Route path="/profile/me" element={<PrivateRoute><OwnProfile /></PrivateRoute>} />
      <Route path="/profile/:userId" element={<PrivateRoute><Profile /></PrivateRoute>} />
      <Route path="/discover" element={<PrivateRoute><Discover /></PrivateRoute>} />
      <Route path="/rooms" element={<PrivateRoute><RoomList /></PrivateRoute>} />
      <Route path="/rooms/:roomId" element={<PrivateRoute><Room /></PrivateRoute>} />
      <Route path="/messages" element={<PrivateRoute><Messages /></PrivateRoute>} />

      {/* Fallback */}
      <Route path="/" element={<Navigate to="/dashboard" replace />} />
      <Route path="*" element={<Navigate to="/dashboard" replace />} />
    </Routes>
  );
}
