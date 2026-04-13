import axios from "axios";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8003/api";

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    "Content-Type": "application/json",
  },
});

// Request interceptor — attach access token
api.interceptors.request.use(
  (config) => {
    if (typeof window !== "undefined") {
      const tokens = localStorage.getItem("tokens");
      if (tokens) {
        const { access } = JSON.parse(tokens);
        if (access) {
          config.headers.Authorization = `Bearer ${access}`;
        }
      }
    }
    return config;
  },
  (error) => Promise.reject(error)
);

// Response interceptor — auto-refresh on 401
api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config;

    if (error.response?.status === 401 && !originalRequest._retry) {
      originalRequest._retry = true;

      try {
        const tokens = localStorage.getItem("tokens");
        if (!tokens) throw new Error("No tokens");

        const { refresh } = JSON.parse(tokens);
        const response = await axios.post(`${API_BASE_URL}/auth/token/refresh/`, {
          refresh,
        });

        const newTokens = {
          access: response.data.access,
          refresh: response.data.refresh || refresh,
        };
        localStorage.setItem("tokens", JSON.stringify(newTokens));

        originalRequest.headers.Authorization = `Bearer ${newTokens.access}`;
        return api(originalRequest);
      } catch {
        localStorage.removeItem("tokens");
        localStorage.removeItem("user");
        if (typeof window !== "undefined") {
          window.location.href = "/login";
        }
        return Promise.reject(error);
      }
    }

    return Promise.reject(error);
  }
);

export default api;
