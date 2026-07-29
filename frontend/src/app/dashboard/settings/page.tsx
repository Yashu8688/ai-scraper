"use client";

import React, { useState, useEffect } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import {
  Save,
  Mail,
  Sliders,
  Key,
  Check,
  AlertCircle,
  Eye,
  EyeOff,
  Users,
  Plus,
  Trash2,
  Loader2,
} from "lucide-react";
import api from "@/lib/api";

type DailyRecipient = { id: number; email: string; name: string | null };

export default function SettingsPage() {
  const router = useRouter();
  const [isAdmin, setIsAdmin] = useState(false);
  const [loadingRole, setLoadingRole] = useState(true);

  // Role validation -- Settings is admin-only, same as Operators.
  useEffect(() => {
    const userRole = localStorage.getItem("role");
    if (userRole !== "admin") {
      router.push("/dashboard");
    } else {
      setIsAdmin(true);
    }
    setLoadingRole(false);
  }, [router]);

  const [minExperience, setMinExperience] = useState(1);
  const [maxExperience, setMaxExperience] = useState(6);
  const [useAiFilter, setUseAiFilter] = useState(false);
  const [smtpHost, setSmtpHost] = useState("");
  const [smtpPort, setSmtpPort] = useState(587);
  const [smtpUser, setSmtpUser] = useState("");
  const [smtpPassword, setSmtpPassword] = useState("");
  const [emailTo, setEmailTo] = useState("");
  const [emailFrom, setEmailFrom] = useState("");
  const [claudeApiKey, setClaudeApiKey] = useState("");
  const [resendApiKey, setResendApiKey] = useState("");
  const [sendgridApiKey, setSendgridApiKey] = useState("");

  const [showPassword, setShowPassword] = useState(false);
  const [showApiKey, setShowApiKey] = useState(false);
  const [showResendKey, setShowResendKey] = useState(false);
  const [showSendgridKey, setShowSendgridKey] = useState(false);
  
  const [successMsg, setSuccessMsg] = useState("");
  const [errorMsg, setErrorMsg] = useState("");

  const [newDailyEmail, setNewDailyEmail] = useState("");
  const [newDailyName, setNewDailyName] = useState("");

  const queryClient = useQueryClient();

  const { data: dailyRecipients = [], isLoading: dailyRecipientsLoading } = useQuery<DailyRecipient[]>({
    queryKey: ["dailyRecipients"],
    queryFn: async () => {
      const response = await api.get("/daily-recipients");
      return response.data;
    },
    enabled: isAdmin,
  });

  const addDailyRecipient = useMutation({
    mutationFn: async () => {
      const response = await api.post("/daily-recipients", {
        email: newDailyEmail.trim(),
        name: newDailyName.trim() || null,
      });
      return response.data;
    },
    onSuccess: () => {
      setNewDailyEmail("");
      setNewDailyName("");
      queryClient.invalidateQueries({ queryKey: ["dailyRecipients"] });
    },
    onError: (err: any) => {
      setErrorMsg(err.response?.data?.detail || "Could not add this email.");
      window.scrollTo({ top: 0, behavior: "smooth" });
    },
  });

  const removeDailyRecipient = useMutation({
    mutationFn: async (id: number) => {
      await api.delete(`/daily-recipients/${id}`);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["dailyRecipients"] });
    },
  });

  // Fetch Current Settings
  const { data: settingsData, isLoading } = useQuery({
    queryKey: ["settings"],
    queryFn: async () => {
      const response = await api.get("/settings");
      return response.data;
    },
    enabled: isAdmin,
  });

  // Load state when settings data is loaded
  useEffect(() => {
    if (settingsData) {
      setMinExperience(settingsData.min_experience);
      setMaxExperience(settingsData.max_experience);
      setUseAiFilter(settingsData.use_ai_filter);
      setSmtpHost(settingsData.smtp_host || "");
      setSmtpPort(settingsData.smtp_port || 587);
      setSmtpUser(settingsData.smtp_user || "");
      setSmtpPassword(settingsData.smtp_password || "");
      setEmailTo(settingsData.email_to || "");
      setEmailFrom(settingsData.email_from || "");
      setClaudeApiKey(settingsData.claude_api_key || "");
      setResendApiKey(settingsData.resend_api_key || "");
      setSendgridApiKey(settingsData.sendgrid_api_key || "");
    }
  }, [settingsData]);

  // Update Settings Mutation
  const updateMutation = useMutation({
    mutationFn: async (updatedSettings: any) => {
      const response = await api.post("/settings", updatedSettings);
      return response.data;
    },
    onSuccess: () => {
      setSuccessMsg("Scraper configuration updated successfully.");
      window.scrollTo({ top: 0, behavior: "smooth" });
      setTimeout(() => setSuccessMsg(""), 5000);
    },
    onError: (err: any) => {
      setErrorMsg(err.response?.data?.detail || "Failed to update scraper settings.");
      window.scrollTo({ top: 0, behavior: "smooth" });
      setTimeout(() => setErrorMsg(""), 5000);
    }
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setSuccessMsg("");
    setErrorMsg("");

    if (minExperience > maxExperience) {
      setErrorMsg("Minimum experience cannot exceed maximum experience.");
      return;
    }

    const payload = {
      min_experience: Number(minExperience),
      max_experience: Number(maxExperience),
      use_ai_filter: useAiFilter,
      smtp_host: smtpHost,
      smtp_port: Number(smtpPort),
      smtp_user: smtpUser,
      smtp_password: smtpPassword,
      email_to: emailTo,
      email_from: emailFrom,
      claude_api_key: claudeApiKey,
      resend_api_key: resendApiKey,
      sendgrid_api_key: sendgridApiKey
    };

    updateMutation.mutate(payload);
  };

  if (loadingRole || !isAdmin) {
    return null;
  }

  if (isLoading) {
    return (
      <div className="space-y-6 animate-pulse">
        <div className="space-y-1.5">
          <div className="h-6 w-36 rounded-xl bg-[#EADFCF]"></div>
          <div className="h-3 w-52 rounded-xl bg-[#EADFCF]"></div>
        </div>
        <div className="h-80 rounded-xl bg-[#EADFCF] border border-[#EADFCF]"></div>
      </div>
    );
  }

  return (
    <div className="space-y-6 max-w-3xl">
      {/* Page Header */}
      <div>
        <h1 className="text-xl font-bold tracking-tight text-[#1E293B]">Aggregator Settings</h1>
        <p className="text-xs text-[#5B5F4A]">
          Configure experience parameters, SMTP email channels, and AI keys
        </p>
      </div>

      <form onSubmit={handleSubmit} className="space-y-5">
        {/* Status Alerts */}
        {successMsg && (
          <div className="flex items-center gap-2.5 rounded-xl border border-emerald-250 bg-emerald-50 p-3.5 text-xs text-emerald-850 font-semibold animate-in fade-in">
            <Check className="h-4.5 w-4.5 shrink-0 text-[#2E7D32]" />
            <span>{successMsg}</span>
          </div>
        )}
        {errorMsg && (
          <div className="flex items-center gap-2.5 rounded-xl border border-red-200 bg-red-50 p-3.5 text-xs text-red-755 font-semibold animate-in fade-in">
            <AlertCircle className="h-4.5 w-4.5 shrink-0 text-[#C53030]" />
            <span>{errorMsg}</span>
          </div>
        )}

        {/* 1. Job Criteria block */}
        <div className="border border-[#EADFCF] bg-[#FFFDFC] p-5 rounded-xl space-y-4 shadow-xs">
          <div className="flex items-center gap-1.5 pb-2.5 border-b border-[#EADFCF]">
            <Sliders className="h-4 w-4 text-[#2F6F5E]" />
            <h3 className="text-xs font-bold uppercase tracking-wider text-[#1E293B]">Job Filters Criteria</h3>
          </div>
          
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-1">
              <label className="text-[10px] font-bold uppercase tracking-wider text-[#5B5F4A]">Minimum Years Experience</label>
              <input
                type="number"
                min="0"
                max="20"
                required
                value={minExperience}
                onChange={(e) => setMinExperience(Number(e.target.value))}
                className="w-full rounded-xl border border-[#EADFCF] bg-[#FFFDFC] px-3 py-2 text-xs text-[#1E293B] outline-none focus:border-[#2F6F5E] focus:ring-2 focus:ring-[#2F6F5E]/10 transition"
              />
            </div>
            <div className="space-y-1">
              <label className="text-[10px] font-bold uppercase tracking-wider text-[#5B5F4A]">Maximum Years Experience</label>
              <input
                type="number"
                min="0"
                max="20"
                required
                value={maxExperience}
                onChange={(e) => setMaxExperience(Number(e.target.value))}
                className="w-full rounded-xl border border-[#EADFCF] bg-[#FFFDFC] px-3 py-2 text-xs text-[#1E293B] outline-none focus:border-[#2F6F5E] focus:ring-2 focus:ring-[#2F6F5E]/10 transition"
              />
            </div>
          </div>
        </div>

        {/* 2. SMTP block */}
        <div className="border border-[#EADFCF] bg-[#FFFDFC] p-5 rounded-xl space-y-4 shadow-xs">
          <div className="flex items-center gap-1.5 pb-2.5 border-b border-[#EADFCF]">
            <Mail className="h-4 w-4 text-[#2F6F5E]" />
            <h3 className="text-xs font-bold uppercase tracking-wider text-[#1E293B]">Email Notification SMTP</h3>
          </div>
          
          <div className="grid gap-4 sm:grid-cols-3">
            <div className="sm:col-span-2 space-y-1">
              <label className="text-[10px] font-bold uppercase tracking-wider text-[#5B5F4A]">SMTP Server Host</label>
              <input
                type="text"
                placeholder="smtp.gmail.com"
                value={smtpHost}
                onChange={(e) => setSmtpHost(e.target.value)}
                className="w-full rounded-xl border border-[#EADFCF] bg-[#FFFDFC] px-3 py-2 text-xs text-[#1E293B] outline-none focus:border-[#2F6F5E] focus:ring-2 focus:ring-[#2F6F5E]/10 transition"
              />
            </div>
            <div className="space-y-1">
              <label className="text-[10px] font-bold uppercase tracking-wider text-[#5B5F4A]">SMTP Port (TLS)</label>
              <input
                type="number"
                placeholder="587"
                value={smtpPort}
                onChange={(e) => setSmtpPort(Number(e.target.value))}
                className="w-full rounded-xl border border-[#EADFCF] bg-[#FFFDFC] px-3 py-2 text-xs text-[#1E293B] outline-none focus:border-[#2F6F5E] focus:ring-2 focus:ring-[#2F6F5E]/10 transition"
              />
            </div>
          </div>

          <div className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-1">
              <label className="text-[10px] font-bold uppercase tracking-wider text-[#5B5F4A]">SMTP Username</label>
              <input
                type="email"
                placeholder="user@gmail.com"
                value={smtpUser}
                onChange={(e) => setSmtpUser(e.target.value)}
                className="w-full rounded-xl border border-[#EADFCF] bg-[#FFFDFC] px-3 py-2 text-xs text-[#1E293B] outline-none focus:border-[#2F6F5E] focus:ring-2 focus:ring-[#2F6F5E]/10 transition"
              />
            </div>
            <div className="space-y-1">
              <label className="text-[10px] font-bold uppercase tracking-wider text-[#5B5F4A]">SMTP App Password</label>
              <div className="relative">
                <input
                  type={showPassword ? "text" : "password"}
                  placeholder="••••••••••••••••"
                  value={smtpPassword}
                  onChange={(e) => setSmtpPassword(e.target.value)}
                  className="w-full rounded-xl border border-[#EADFCF] bg-[#FFFDFC] px-3 py-2 pr-10 text-xs text-[#1E293B] outline-none focus:border-[#2F6F5E] focus:ring-2 focus:ring-[#2F6F5E]/10 transition"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute inset-y-0 right-0 flex items-center pr-3 text-[#5B5F4A] hover:text-[#1E293B]"
                >
                  {showPassword ? <EyeOff className="h-3.5 w-3.5" /> : <Eye className="h-3.5 w-3.5" />}
                </button>
              </div>
            </div>
          </div>

          <div className="space-y-1">
            <label className="text-[10px] font-bold uppercase tracking-wider text-[#5B5F4A]">Sender Address (From)</label>
            <input
              type="email"
              placeholder="sender@gmail.com"
              value={emailFrom}
              onChange={(e) => setEmailFrom(e.target.value)}
              className="w-full rounded-xl border border-[#EADFCF] bg-[#FFFDFC] px-3 py-2 text-xs text-[#1E293B] outline-none focus:border-[#2F6F5E] focus:ring-2 focus:ring-[#2F6F5E]/10 transition"
            />
          </div>

          {/* Daily Digest Recipients — replaces the old single EMAIL_TO text field with an
              editable list. Adding/removing here changes who receives the automated nightly
              email; it's separate from the "Send to clients" list on the Domain Jobs page. */}
          <div className="space-y-2">
            <label className="text-[10px] font-bold uppercase tracking-wider text-[#5B5F4A] flex items-center gap-1.5">
              <Users className="h-3 w-3" />
              Daily Digest Recipients
            </label>

            <div className="rounded-xl border border-[#EADFCF] bg-[#FFF9F0] divide-y divide-[#EADFCF]">
              {dailyRecipientsLoading ? (
                <div className="flex items-center gap-2 p-3 text-xs text-[#5B5F4A]">
                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                  <span>Loading recipients…</span>
                </div>
              ) : dailyRecipients.length === 0 ? (
                <div className="p-3 text-xs text-[#5B5F4A]">
                  No recipients saved yet. Add one below to receive the automated nightly digest.
                </div>
              ) : (
                dailyRecipients.map((r) => (
                  <div key={r.id} className="flex items-center gap-2.5 p-2.5">
                    <span className="flex-1 min-w-0 text-xs">
                      <span className="font-semibold text-[#1E293B] block truncate">{r.email}</span>
                      {r.name && <span className="text-[#5B5F4A] text-[11px]">{r.name}</span>}
                    </span>
                    <button
                      type="button"
                      onClick={() => removeDailyRecipient.mutate(r.id)}
                      className="text-[#C53030] hover:bg-red-50 rounded-lg p-1 transition shrink-0"
                      title={`Remove ${r.email}`}
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                    </button>
                  </div>
                ))
              )}
            </div>

            <div className="flex flex-col sm:flex-row gap-2">
              <input
                type="email"
                value={newDailyEmail}
                onChange={(e) => setNewDailyEmail(e.target.value)}
                placeholder="receiver@gmail.com"
                className="flex-1 rounded-xl border border-[#EADFCF] bg-[#FFFDFC] px-3 py-2 text-xs text-[#1E293B] outline-none focus:border-[#2F6F5E] focus:ring-2 focus:ring-[#2F6F5E]/10 transition"
              />
              <input
                type="text"
                value={newDailyName}
                onChange={(e) => setNewDailyName(e.target.value)}
                placeholder="Name (optional)"
                className="sm:w-40 rounded-xl border border-[#EADFCF] bg-[#FFFDFC] px-3 py-2 text-xs text-[#1E293B] outline-none focus:border-[#2F6F5E] focus:ring-2 focus:ring-[#2F6F5E]/10 transition"
              />
              <button
                type="button"
                onClick={() => addDailyRecipient.mutate()}
                disabled={!newDailyEmail.trim() || addDailyRecipient.isPending}
                className="inline-flex items-center justify-center gap-1.5 rounded-xl border border-[#EADFCF] bg-[#FFFDFC] px-3 py-2 text-xs font-semibold text-[#1E293B] hover:bg-[#FFF9F0] transition disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {addDailyRecipient.isPending ? (
                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                ) : (
                  <Plus className="h-3.5 w-3.5" />
                )}
                <span>Add</span>
              </button>
            </div>
          </div>
        </div>

        {/* 3. API keys block */}
        <div className="border border-[#EADFCF] bg-[#FFFDFC] p-5 rounded-xl space-y-4 shadow-xs">
          <div className="flex items-center gap-1.5 pb-2.5 border-b border-[#EADFCF]">
            <Key className="h-4 w-4 text-[#2F6F5E]" />
            <h3 className="text-xs font-bold uppercase tracking-wider text-[#1E293B]">Authorization Keys</h3>
          </div>
          
          <div className="space-y-1">
            <label className="text-[10px] font-bold uppercase tracking-wider text-[#5B5F4A]">Claude Anthropic API Key</label>
            <div className="relative">
              <input
                type={showApiKey ? "text" : "password"}
                placeholder="sk-ant-api03-..."
                value={claudeApiKey}
                onChange={(e) => setClaudeApiKey(e.target.value)}
                className="w-full rounded-xl border border-[#EADFCF] bg-[#FFFDFC] px-3 py-2 pr-10 text-xs text-[#1E293B] outline-none focus:border-[#2F6F5E] focus:ring-2 focus:ring-[#2F6F5E]/10 transition"
              />
              <button
                type="button"
                onClick={() => setShowApiKey(!showApiKey)}
                className="absolute inset-y-0 right-0 flex items-center pr-3 text-[#5B5F4A] hover:text-[#1E293B]"
              >
                {showApiKey ? <EyeOff className="h-3.5 w-3.5" /> : <Eye className="h-3.5 w-3.5" />}
              </button>
            </div>
          </div>

          <div className="space-y-1">
            <label className="text-[10px] font-bold uppercase tracking-wider text-[#5B5F4A]">SendGrid API Key</label>
            <p className="text-[9px] text-[#5B5F4A] leading-normal font-medium">Preferred sender for the on-demand Domain Jobs report (Render blocks direct SMTP). Requires Single Sender Verification for the Sender Address above.</p>
            <div className="relative">
              <input
                type={showSendgridKey ? "text" : "password"}
                placeholder="SG...."
                value={sendgridApiKey}
                onChange={(e) => setSendgridApiKey(e.target.value)}
                className="w-full rounded-xl border border-[#EADFCF] bg-[#FFFDFC] px-3 py-2 pr-10 text-xs text-[#1E293B] outline-none focus:border-[#2F6F5E] focus:ring-2 focus:ring-[#2F6F5E]/10 transition"
              />
              <button
                type="button"
                onClick={() => setShowSendgridKey(!showSendgridKey)}
                className="absolute inset-y-0 right-0 flex items-center pr-3 text-[#5B5F4A] hover:text-[#1E293B]"
              >
                {showSendgridKey ? <EyeOff className="h-3.5 w-3.5" /> : <Eye className="h-3.5 w-3.5" />}
              </button>
            </div>
          </div>

          <div className="space-y-1">
            <label className="text-[10px] font-bold uppercase tracking-wider text-[#5B5F4A]">Resend API Key</label>
            <p className="text-[9px] text-[#5B5F4A] leading-normal font-medium">Fallback if SendGrid isn't set. Resend's shared sender can only deliver to your own email unless a domain is verified.</p>
            <div className="relative">
              <input
                type={showResendKey ? "text" : "password"}
                placeholder="re_..."
                value={resendApiKey}
                onChange={(e) => setResendApiKey(e.target.value)}
                className="w-full rounded-xl border border-[#EADFCF] bg-[#FFFDFC] px-3 py-2 pr-10 text-xs text-[#1E293B] outline-none focus:border-[#2F6F5E] focus:ring-2 focus:ring-[#2F6F5E]/10 transition"
              />
              <button
                type="button"
                onClick={() => setShowResendKey(!showResendKey)}
                className="absolute inset-y-0 right-0 flex items-center pr-3 text-[#5B5F4A] hover:text-[#1E293B]"
              >
                {showResendKey ? <EyeOff className="h-3.5 w-3.5" /> : <Eye className="h-3.5 w-3.5" />}
              </button>
            </div>
          </div>
        </div>

        {/* Form Action Submit */}
        <div className="flex justify-end pt-2">
          <button
            type="submit"
            disabled={updateMutation.isPending}
            className="btn-primary flex items-center gap-1.5 text-xs py-2 px-6 font-semibold bg-[#C67C2E] text-white hover:bg-[#A9621C] rounded-xl"
          >
            {updateMutation.isPending ? (
              <div className="h-4 w-4 animate-spin rounded-full border-2 border-white border-t-transparent"></div>
            ) : (
              <>
                <Save className="h-4 w-4" />
                <span>Save Scraper Settings</span>
              </>
            )}
          </button>
        </div>
      </form>
    </div>
  );
}
