"use client";

import React, { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Send,
  ChevronDown,
  FileSpreadsheet,
  CheckCircle2,
  AlertCircle,
  Loader2,
  CalendarClock,
  ListChecks,
} from "lucide-react";
import api from "@/lib/api";

const DOMAIN_OPTIONS = [
  { value: "cyber", label: "Cyber Security", emoji: "🇺🇸" },
  { value: "data", label: "Data Engineering / Analytics", emoji: "📊" },
  { value: "java", label: "Java Developer", emoji: "☕" },
  { value: "dotnet", label: ".NET Developer", emoji: "🔷" },
];

export default function DomainJobsPage() {
  const queryClient = useQueryClient();
  const [domain, setDomain] = useState("cyber");
  const [feedback, setFeedback] = useState<{ type: "success" | "error"; message: string } | null>(null);

  const { data: status, isLoading: statusLoading } = useQuery({
    queryKey: ["domainReportStatus", domain],
    queryFn: async () => {
      const response = await api.get("/domain-reports/latest", { params: { domain } });
      return response.data;
    },
  });

  const sendMutation = useMutation({
    mutationFn: async () => {
      const response = await api.post("/domain-reports/send", { domain });
      return response.data;
    },
    onSuccess: (data) => {
      if (data.success) {
        setFeedback({ type: "success", message: data.message });
      } else {
        setFeedback({ type: "error", message: data.message || "No excel found" });
      }
      queryClient.invalidateQueries({ queryKey: ["activityLogs"] });
    },
    onError: (err: any) => {
      setFeedback({
        type: "error",
        message: err.response?.data?.detail || "Failed to send report.",
      });
    },
  });

  const handleDomainChange = (value: string) => {
    setDomain(value);
    setFeedback(null);
  };

  const handleSend = () => {
    setFeedback(null);
    sendMutation.mutate();
  };

  const selected = DOMAIN_OPTIONS.find((d) => d.value === domain);

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div>
        <h1 className="text-xl font-bold tracking-tight text-[#1E293B]">Domain Jobs</h1>
        <p className="text-xs text-[#5B5F4A]">
          Resend the latest stored report for a specific domain, on demand
        </p>
      </div>

      {/* Send Panel */}
      <div className="border border-[#EADFCF] bg-[#FFFDFC] p-6 rounded-xl shadow-xs space-y-5 max-w-xl">
        <div className="space-y-1">
          <label className="text-[10px] font-bold uppercase tracking-wider text-[#5B5F4A]">Domain</label>
          <div className="relative">
            <select
              value={domain}
              onChange={(e) => handleDomainChange(e.target.value)}
              className="w-full appearance-none rounded-xl border border-[#EADFCF] bg-[#FFFDFC] pl-3 pr-8.5 py-2.5 text-sm text-[#1E293B] outline-none focus:border-[#2F6F5E] focus:ring-2 focus:ring-[#2F6F5E]/10 transition cursor-pointer font-semibold"
            >
              {DOMAIN_OPTIONS.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.emoji} {opt.label}
                </option>
              ))}
            </select>
            <ChevronDown className="absolute right-3.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-[#5B5F4A] pointer-events-none" />
          </div>
        </div>

        {/* Latest stored report status */}
        <div className="rounded-xl border border-[#EADFCF] bg-[#FFF9F0] p-4 text-xs text-[#5B5F4A] space-y-2">
          {statusLoading ? (
            <div className="flex items-center gap-2">
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
              <span>Checking stored reports…</span>
            </div>
          ) : status?.found ? (
            <>
              <div className="flex items-center gap-2 font-semibold text-[#1E293B]">
                <FileSpreadsheet className="h-3.5 w-3.5 text-[#2F6F5E]" />
                <span>Latest {status.label} report is ready to send</span>
              </div>
              <div className="flex items-center gap-1.5">
                <CalendarClock className="h-3 w-3" />
                <span>Stored on {status.report_date}</span>
              </div>
              {typeof status.job_count === "number" && (
                <div className="flex items-center gap-1.5">
                  <ListChecks className="h-3 w-3" />
                  <span>{status.job_count} jobs in this report</span>
                </div>
              )}
            </>
          ) : (
            <div className="flex items-center gap-2">
              <AlertCircle className="h-3.5 w-3.5" />
              <span>No excel found for {selected?.label} yet.</span>
            </div>
          )}
        </div>

        {/* Feedback banner */}
        {feedback && (
          <div
            className={`flex items-center gap-2 rounded-xl border p-3 text-xs font-semibold ${
              feedback.type === "success"
                ? "border-green-200 bg-green-50 text-[#2E7D32]"
                : "border-red-200 bg-red-50 text-[#C53030]"
            }`}
          >
            {feedback.type === "success" ? (
              <CheckCircle2 className="h-4 w-4 shrink-0" />
            ) : (
              <AlertCircle className="h-4 w-4 shrink-0" />
            )}
            <span>{feedback.message}</span>
          </div>
        )}

        {/* Send button */}
        <button
          onClick={handleSend}
          disabled={sendMutation.isPending || !status?.found}
          className="btn-primary inline-flex items-center gap-1.5 text-xs py-2.5 px-5 font-semibold bg-[#C67C2E] text-white hover:bg-[#A9621C] rounded-xl disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {sendMutation.isPending ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <Send className="h-4 w-4" />
          )}
          <span>{sendMutation.isPending ? "Sending..." : "Send"}</span>
        </button>
      </div>
    </div>
  );
}
