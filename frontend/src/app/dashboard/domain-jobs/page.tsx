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
  Plus,
  Trash2,
  Users,
} from "lucide-react";
import api from "@/lib/api";

const DOMAIN_OPTIONS = [
  { value: "data", label: "Data roles" },
  { value: "java", label: "Java roles" },
  { value: "dotnet", label: ".NET roles" },
  { value: "cyber", label: "Cyber roles" },
];

type Recipient = { id: number; email: string; name: string | null };

export default function DomainJobsPage() {
  const queryClient = useQueryClient();
  const [domain, setDomain] = useState("cyber");
  const [feedback, setFeedback] = useState<{ type: "success" | "error"; message: string } | null>(null);
  const [selectedIds, setSelectedIds] = useState<number[]>([]);
  const [newEmail, setNewEmail] = useState("");
  const [newName, setNewName] = useState("");

  const { data: status, isLoading: statusLoading } = useQuery({
    queryKey: ["domainReportStatus", domain],
    queryFn: async () => {
      const response = await api.get("/domain-reports/latest", { params: { domain } });
      return response.data;
    },
  });

  const { data: recipients = [], isLoading: recipientsLoading } = useQuery<Recipient[]>({
    queryKey: ["recipients"],
    queryFn: async () => {
      const response = await api.get("/recipients");
      return response.data;
    },
  });

  const addRecipient = useMutation({
    mutationFn: async () => {
      const response = await api.post("/recipients", {
        email: newEmail.trim(),
        name: newName.trim() || null,
      });
      return response.data;
    },
    onSuccess: (created: Recipient) => {
      setNewEmail("");
      setNewName("");
      setFeedback(null);
      // Newly added clients start selected — that is why they were added.
      setSelectedIds((prev) => [...prev, created.id]);
      queryClient.invalidateQueries({ queryKey: ["recipients"] });
    },
    onError: (err: any) => {
      setFeedback({
        type: "error",
        message: err.response?.data?.detail || "Could not add this email.",
      });
    },
  });

  const removeRecipient = useMutation({
    mutationFn: async (id: number) => {
      await api.delete(`/recipients/${id}`);
      return id;
    },
    onSuccess: (id) => {
      setSelectedIds((prev) => prev.filter((x) => x !== id));
      queryClient.invalidateQueries({ queryKey: ["recipients"] });
    },
  });

  const sendMutation = useMutation({
    mutationFn: async () => {
      const response = await api.post("/domain-reports/send", {
        domain,
        recipient_ids: selectedIds,
      });
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
        <h1 className="text-xl font-bold tracking-tight text-[#1E293B]">Email</h1>
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
                  {opt.label}
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

        {/* Client recipients */}
        <div className="space-y-2">
          <label className="text-[10px] font-bold uppercase tracking-wider text-[#5B5F4A] flex items-center gap-1.5">
            <Users className="h-3 w-3" />
            Send to clients
          </label>

          <div className="rounded-xl border border-[#EADFCF] bg-[#FFF9F0] divide-y divide-[#EADFCF]">
            {recipientsLoading ? (
              <div className="flex items-center gap-2 p-3 text-xs text-[#5B5F4A]">
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
                <span>Loading clients…</span>
              </div>
            ) : recipients.length === 0 ? (
              <div className="p-3 text-xs text-[#5B5F4A]">
                No clients saved yet. Add one below — the report goes to the addresses you tick here.
              </div>
            ) : (
              recipients.map((r) => (
                <label
                  key={r.id}
                  className="flex items-center gap-2.5 p-2.5 cursor-pointer hover:bg-[#FFFDFC] transition"
                >
                  <input
                    type="checkbox"
                    checked={selectedIds.includes(r.id)}
                    onChange={(e) =>
                      setSelectedIds((prev) =>
                        e.target.checked ? [...prev, r.id] : prev.filter((x) => x !== r.id)
                      )
                    }
                    className="h-3.5 w-3.5 accent-[#2F6F5E] cursor-pointer"
                  />
                  <span className="flex-1 min-w-0 text-xs">
                    <span className="font-semibold text-[#1E293B] block truncate">{r.email}</span>
                    {r.name && <span className="text-[#5B5F4A] text-[11px]">{r.name}</span>}
                  </span>
                  <button
                    type="button"
                    onClick={(e) => {
                      e.preventDefault();
                      removeRecipient.mutate(r.id);
                    }}
                    className="text-[#C53030] hover:bg-red-50 rounded-lg p-1 transition shrink-0"
                    title={`Remove ${r.email}`}
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                  </button>
                </label>
              ))
            )}
          </div>

          {/* Add a new client */}
          <div className="flex flex-col sm:flex-row gap-2">
            <input
              type="email"
              value={newEmail}
              onChange={(e) => setNewEmail(e.target.value)}
              placeholder="client@company.com"
              className="flex-1 rounded-xl border border-[#EADFCF] bg-[#FFFDFC] px-3 py-2 text-xs text-[#1E293B] outline-none focus:border-[#2F6F5E] focus:ring-2 focus:ring-[#2F6F5E]/10 transition"
            />
            <input
              type="text"
              value={newName}
              onChange={(e) => setNewName(e.target.value)}
              placeholder="Name (optional)"
              className="sm:w-40 rounded-xl border border-[#EADFCF] bg-[#FFFDFC] px-3 py-2 text-xs text-[#1E293B] outline-none focus:border-[#2F6F5E] focus:ring-2 focus:ring-[#2F6F5E]/10 transition"
            />
            <button
              type="button"
              onClick={() => addRecipient.mutate()}
              disabled={!newEmail.trim() || addRecipient.isPending}
              className="inline-flex items-center justify-center gap-1.5 rounded-xl border border-[#EADFCF] bg-[#FFFDFC] px-3 py-2 text-xs font-semibold text-[#1E293B] hover:bg-[#FFF9F0] transition disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {addRecipient.isPending ? (
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
              ) : (
                <Plus className="h-3.5 w-3.5" />
              )}
              <span>Add</span>
            </button>
          </div>

          {selectedIds.length === 0 && recipients.length > 0 && (
            <p className="text-[11px] text-[#5B5F4A]">
              No client ticked — the report will go to the default digest recipients.
            </p>
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
