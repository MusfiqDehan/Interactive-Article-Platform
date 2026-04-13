"use client";

import { createContext, useContext, useEffect, useState, useCallback, ReactNode } from "react";
import api from "./api";
import { User, AuthTokens, LoginCredentials, RegisterData } from "./types";

interface AuthContextType {
  user: User | null;
  tokens: AuthTokens | null;
  isLoading: boolean;
  isAuthenticated: boolean;
  login: (credentials: LoginCredentials) => Promise<void>;
  register: (data: RegisterData) => Promise<void>;
  logout: () => Promise<void>;
  updateProfile: (data: Partial<User>) => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [tokens, setTokens] = useState<AuthTokens | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  const fetchProfile = useCallback(async () => {
    try {
      const response = await api.get("/auth/profile/");
      setUser(response.data);
      localStorage.setItem("user", JSON.stringify(response.data));
    } catch {
      setUser(null);
      setTokens(null);
      localStorage.removeItem("tokens");
      localStorage.removeItem("user");
    }
  }, []);

  useEffect(() => {
    const storedTokens = localStorage.getItem("tokens");
    const storedUser = localStorage.getItem("user");

    if (storedTokens) {
      setTokens(JSON.parse(storedTokens));
      if (storedUser) {
        setUser(JSON.parse(storedUser));
      }
      fetchProfile();
    }
    setIsLoading(false);
  }, [fetchProfile]);

  const login = async (credentials: LoginCredentials) => {
    const response = await api.post("/auth/login/", credentials);
    const { access, refresh } = response.data;
    const newTokens = { access, refresh };
    setTokens(newTokens);
    localStorage.setItem("tokens", JSON.stringify(newTokens));
    await fetchProfile();
  };

  const register = async (data: RegisterData) => {
    const response = await api.post("/auth/register/", data);
    const { tokens: newTokens, user: newUser } = response.data;
    setTokens(newTokens);
    setUser(newUser);
    localStorage.setItem("tokens", JSON.stringify(newTokens));
    localStorage.setItem("user", JSON.stringify(newUser));
  };

  const logout = async () => {
    try {
      if (tokens?.refresh) {
        await api.post("/auth/logout/", { refresh: tokens.refresh });
      }
    } catch {
      // Ignore logout errors
    } finally {
      setUser(null);
      setTokens(null);
      localStorage.removeItem("tokens");
      localStorage.removeItem("user");
    }
  };

  const updateProfile = async (data: Partial<User>) => {
    const response = await api.patch("/auth/profile/", data);
    setUser(response.data);
    localStorage.setItem("user", JSON.stringify(response.data));
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        tokens,
        isLoading,
        isAuthenticated: !!user,
        login,
        register,
        logout,
        updateProfile,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
}
