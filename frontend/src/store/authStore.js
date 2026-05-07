import { create } from "zustand";
import { persist } from "zustand/middleware";

export const useAuthStore = create(
  persist(
    (set) => ({
      accessToken: null,
      user: null,
      role: null,

      setAuth: (accessToken, role) =>
        set({ accessToken, role }),

      setUser: (user) => set({ user }),

      setAccessToken: (accessToken) => set({ accessToken }),

      logout: () => set({ accessToken: null, user: null, role: null }),
    }),
    {
      name: "rv-auth",
      partialize: (state) => ({ role: state.role }),
      // Don't persist access token in localStorage — keep in memory only
    }
  )
);
