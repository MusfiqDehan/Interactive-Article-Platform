"use client";

import { useRouter } from "next/navigation";
import { useState, FormEvent } from "react";
import {
  AuthPanel,
  AuthField,
  AuthSubmit,
} from "@/components/storyloom/AuthPanel";
import { useAuth } from "@/lib/auth";

export default function LoginPage() {
  const router = useRouter();
  const { login } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [isLoading, setIsLoading] = useState(false);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError("");
    setIsLoading(true);

    try {
      await login({ email, password });
      router.push("/");
    } catch (err: unknown) {
      const error = err as { response?: { data?: { detail?: string } } };
      setError(
        error.response?.data?.detail ||
          "Invalid credentials. Please try again.",
      );
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <AuthPanel mode="login" error={error}>
      <form onSubmit={handleSubmit} className="sl-form">
        <AuthField
          id="email"
          name="email"
          label="Email address"
          type="email"
          autoComplete="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          placeholder="you@example.com"
          required
        />
        <AuthField
          id="password"
          name="password"
          label="Password"
          type="password"
          autoComplete="current-password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          placeholder="Enter your password"
          required
        />
        <AuthSubmit loading={isLoading} pending="Signing in…">
          Sign in to Storyloom
        </AuthSubmit>
      </form>
    </AuthPanel>
  );
}
