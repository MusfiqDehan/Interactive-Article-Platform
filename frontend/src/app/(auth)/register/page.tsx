"use client";

import { useRouter } from "next/navigation";
import { useState, FormEvent } from "react";
import {
  AuthPanel,
  AuthField,
  AuthSubmit,
} from "@/components/storyloom/AuthPanel";
import { useAuth } from "@/lib/auth";

export default function RegisterPage() {
  const router = useRouter();
  const { register } = useAuth();
  const [formData, setFormData] = useState({
    email: "",
    username: "",
    first_name: "",
    last_name: "",
    password: "",
    password_confirm: "",
  });
  const [error, setError] = useState("");
  const [isLoading, setIsLoading] = useState(false);

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setFormData((prev) => ({ ...prev, [e.target.name]: e.target.value }));
  };

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError("");

    if (formData.password !== formData.password_confirm) {
      setError("Passwords do not match.");
      return;
    }

    setIsLoading(true);
    try {
      await register(formData);
      router.push("/");
    } catch (err: unknown) {
      const error = err as { response?: { data?: Record<string, string[]> } };
      const data = error.response?.data;
      if (data) {
        const firstError = Object.values(data)[0];
        setError(
          Array.isArray(firstError) ? firstError[0] : String(firstError),
        );
      } else {
        setError("Registration failed. Please try again.");
      }
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <AuthPanel mode="register" error={error}>
      <form onSubmit={handleSubmit} className="sl-form">
        <div className="sl-form-row">
          <AuthField
            id="first_name"
            name="first_name"
            label="First name"
            autoComplete="given-name"
            value={formData.first_name}
            onChange={handleChange}
            placeholder="Alex"
          />
          <AuthField
            id="last_name"
            name="last_name"
            label="Last name"
            autoComplete="family-name"
            value={formData.last_name}
            onChange={handleChange}
            placeholder="Morgan"
          />
        </div>
        <AuthField
          id="username"
          name="username"
          label="Username"
          autoComplete="username"
          value={formData.username}
          onChange={handleChange}
          placeholder="Your public name"
          required
        />
        <AuthField
          id="email"
          name="email"
          label="Email address"
          type="email"
          autoComplete="email"
          value={formData.email}
          onChange={handleChange}
          placeholder="you@example.com"
          required
        />
        <div className="sl-form-row">
          <AuthField
            id="password"
            name="password"
            label="Password"
            type="password"
            autoComplete="new-password"
            value={formData.password}
            onChange={handleChange}
            placeholder="Create a password"
            required
          />
          <AuthField
            id="password_confirm"
            name="password_confirm"
            label="Confirm password"
            type="password"
            autoComplete="new-password"
            value={formData.password_confirm}
            onChange={handleChange}
            placeholder="Repeat password"
            required
          />
        </div>
        <AuthSubmit loading={isLoading} pending="Creating account…">
          Create your account
        </AuthSubmit>
      </form>
    </AuthPanel>
  );
}
