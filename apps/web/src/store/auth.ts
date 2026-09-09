import { create } from "zustand";
import { login as apiLogin, signup as apiSignup } from "@/lib/api";

interface AuthState {
  token: string | null;
  userId: string | null;
  email: string | null;
  isAuthenticated: boolean;
  hydrated: boolean;
  error: string | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  signup: (email: string, password: string) => Promise<void>;
  logout: () => void;
  hydrate: () => void;
}

export const useAuthStore = create<AuthState>((set) => ({
  token: null,
  userId: null,
  email: null,
  isAuthenticated: false,
  hydrated: false,
  error: null,
  loading: false,

  login: async (email, password) => {
    set({ loading: true, error: null });
    try {
      const res = await apiLogin(email, password);
      localStorage.setItem("cortexbi_token", res.token);
      localStorage.setItem("cortexbi_user", JSON.stringify({ userId: res.user_id, email: res.email }));
      set({ token: res.token, userId: res.user_id, email: res.email, isAuthenticated: true, loading: false });
    } catch (err) {
      set({ loading: false, error: err instanceof Error ? err.message : "Login failed" });
    }
  },

  signup: async (email, password) => {
    set({ loading: true, error: null });
    try {
      const res = await apiSignup(email, password);
      localStorage.setItem("cortexbi_token", res.token);
      localStorage.setItem("cortexbi_user", JSON.stringify({ userId: res.user_id, email: res.email }));
      set({ token: res.token, userId: res.user_id, email: res.email, isAuthenticated: true, loading: false });
    } catch (err) {
      set({ loading: false, error: err instanceof Error ? err.message : "Signup failed" });
    }
  },

  logout: () => {
    localStorage.removeItem("cortexbi_token");
    localStorage.removeItem("cortexbi_user");
    set({ token: null, userId: null, email: null, isAuthenticated: false });
  },

  hydrate: () => {
    try {
      const token = localStorage.getItem("cortexbi_token");
      const userStr = localStorage.getItem("cortexbi_user");
      if (token && userStr) {
        const user = JSON.parse(userStr);
        set({ token, userId: user.userId, email: user.email, isAuthenticated: true, hydrated: true });
      } else {
        set({ hydrated: true });
      }
    } catch {
      set({ hydrated: true });
    }
  },
}));
