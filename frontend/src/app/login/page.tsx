"use client";

import React, { useState } from "react";
import { useRouter } from "next/navigation";
import { Shield, AlertCircle, Eye, EyeOff } from "lucide-react";
import api from "@/lib/api";

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);

    if (!email || !password) {
      setError("Please fill in all fields.");
      setLoading(false);
      return;
    }

    try {
      const response = await api.post("/auth/login", { email, password });
      const { access_token, role, email: userEmail } = response.data;

      localStorage.setItem("token", access_token);
      localStorage.setItem("role", role);
      localStorage.setItem("email", userEmail);

      router.push("/dashboard");
    } catch (err: any) {
      setError(
        err.response?.data?.detail || "Authentication failed. Please verify credentials."
      );
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="relative flex min-h-screen items-center justify-center bg-[#FFFDF8] px-4 py-12">
      <div className="w-full max-w-sm z-10">
        
        {/* Logo and branding details */}
        <div className="flex flex-col items-center mb-6">
          <div className="flex h-11 w-11 items-center justify-center rounded-xl border border-[#EADFCF] bg-[#FFF9F0] text-[#2F6F5E] shadow-xs mb-3.5">
            <Shield className="h-5.5 w-5.5" />
          </div>
          <h2 className="text-xl font-bold tracking-tight text-[#1E293B]">
            Sign in to Console
          </h2>
        </div>

        {/* Elegant White Form Card */}
        <div className="border border-[#EADFCF] bg-[#FFF9F0] p-6 rounded-xl shadow-xs">
          <form onSubmit={handleSubmit} className="space-y-4">
            {error && (
              <div className="flex items-center gap-2 rounded-xl border border-red-200 bg-red-50 p-3 text-xs text-[#C53030] font-semibold animate-in fade-in">
                <AlertCircle className="h-4 w-4 shrink-0 text-[#C53030]" />
                <span className="leading-normal">{error}</span>
              </div>
            )}

            {/* Email Field */}
            <div className="space-y-1">
              <label htmlFor="email" className="text-[10px] font-bold uppercase tracking-wider text-[#5B5F4A]">
                Email Address
              </label>
              <input
                id="email"
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="admin@cyberjobs.com"
                className="w-full rounded-xl border border-[#EADFCF] bg-[#FFFDFC] px-3 py-2 text-xs text-[#1E293B] placeholder-gray-400 transition focus:border-[#2F6F5E] focus:ring-2 focus:ring-[#2F6F5E]/10 outline-none"
              />
            </div>

            {/* Password Field */}
            <div className="space-y-1">
              <label htmlFor="password" className="text-[10px] font-bold uppercase tracking-wider text-[#5B5F4A]">
                Password
              </label>
              <div className="relative">
                <input
                  id="password"
                  type={showPassword ? "text" : "password"}
                  required
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••"
                  className="w-full rounded-xl border border-[#EADFCF] bg-[#FFFDFC] px-3 py-2 pr-10 text-xs text-[#1E293B] placeholder-gray-400 transition focus:border-[#2F6F5E] focus:ring-2 focus:ring-[#2F6F5E]/10 outline-none"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute inset-y-0 right-0 flex items-center pr-3 text-[#5B5F4A]/70 hover:text-[#1E293B]"
                >
                  {showPassword ? <EyeOff className="h-3.5 w-3.5" /> : <Eye className="h-3.5 w-3.5" />}
                </button>
              </div>
            </div>

            {/* Submit CTA button */}
            <button
              type="submit"
              disabled={loading}
              className="flex w-full items-center justify-center rounded-xl bg-[#C67C2E] px-4 py-2.5 text-xs font-semibold text-white transition hover:bg-[#A9621C] active:scale-[0.98] disabled:opacity-50 pointer-events-auto cursor-pointer"
            >
              {loading ? (
                <div className="h-4 w-4 animate-spin rounded-full border-2 border-white border-t-transparent"></div>
              ) : (
                "Continue"
              )}
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}
