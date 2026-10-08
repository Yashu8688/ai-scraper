"use client";

import React, { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  FileText,
  Plus,
  X,
  Trash2,
  Loader2,
  AlertCircle,
  ChevronDown,
  ChevronUp,
  Users,
  Power,
  CalendarClock,
  CalendarOff,
  ListChecks,
  Download,
} from "lucide-react";
import api from "@/lib/api";

type Resume = {
  id: number;
  candidate_name: string;
  original_filename: string;
  is_active: boolean;
  include_weekends: boolean;
  created_at: string;
};

type ResumeRecipient = { id: number; resume_id: number; email: string; name: string | null };

// FastAPI's `detail` is a plain string for a raised HTTPException, but for a request
// validation failure (422, before the endpoint even runs) it's an array of
// {type, loc, msg, input} objects instead -- rendering that array directly as JSX throws
// (React error #31, "objects are not valid as a child"), so always reduce it to a string.
function extractErrorMessage(err: any, fallback: string): string {
  const detail = err?.response?.data?.detail;
  if (!detail) return fallback;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    return detail.map((d) => (typeof d === "string" ? d : d?.msg || JSON.stringify(d))).join("; ");
  }
  return fallback;
}

function ResumeRecipients({ resumeId }: { resumeId: number }) {
  const queryClient = useQueryClient();
  const [newEmail, setNewEmail] = useState("");
  const [newName, setNewName] = useState("");
  const [error, setError] = useState("");

  const { data: recipients = [], isLoading } = useQuery<ResumeRecipient[]>({
    queryKey: ["resumeRecipients", resumeId],
    queryFn: async () => {
      const response = await api.get(`/resumes/${resumeId}/recipients`);
      return response.data;
    },
  });

  const addRecipient = useMutation({
    mutationFn: async () => {
      const response = await api.post(`/resumes/${resumeId}/recipients`, {
        email: newEmail.trim(),
        name: newName.trim() || null,
      });
      return response.data;
    },
    onSuccess: () => {
      setNewEmail("");
      setNewName("");
      setError("");
      queryClient.invalidateQueries({ queryKey: ["resumeRecipients", resumeId] });
    },
    onError: (err: any) => {
      setError(extractErrorMessage(err, "Could not add this email."));
    },
  });

  const removeRecipient = useMutation({
    mutationFn: async (id: number) => {
      await api.delete(`/resumes/${resumeId}/recipients/${id}`);
      return id;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["resumeRecipients", resumeId] });
    },
  });

  return (
    <div className="space-y-2 pt-3 mt-3 border-t border-[#EADFCF]">
      <label className="text-[10px] font-bold uppercase tracking-wider text-[#5B5F4A] flex items-center gap-1.5">
        <Users className="h-3 w-3" />
        Send matched jobs to
      </label>

      <div className="rounded-xl border border-[#EADFCF] bg-[#FFF9F0] divide-y divide-[#EADFCF]">
        {isLoading ? (
          <div className="flex items-center gap-2 p-3 text-xs text-[#5B5F4A]">
            <Loader2 className="h-3.5 w-3.5 animate-spin" />
            <span>Loading recipients…</span>
          </div>
        ) : recipients.length === 0 ? (
          <div className="p-3 text-xs text-[#5B5F4A]">
            No recipients yet — add one below. Without a recipient, this resume's matches are saved but never emailed.
          </div>
        ) : (
          recipients.map((r) => (
            <div key={r.id} className="flex items-center gap-2.5 p-2.5">
              <span className="flex-1 min-w-0 text-xs">
                <span className="font-semibold text-[#1E293B] truncate block">{r.email}</span>
                {r.name && <span className="text-[#5B5F4A] text-[11px]">{r.name}</span>}
              </span>
              <button
                type="button"
                onClick={() => removeRecipient.mutate(r.id)}
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
          value={newEmail}
          onChange={(e) => setNewEmail(e.target.value)}
          placeholder="recipient@company.com"
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
          {addRecipient.isPending ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Plus className="h-3.5 w-3.5" />}
          <span>Add</span>
        </button>
      </div>
      {error && <p className="text-[11px] text-[#C53030] font-semibold">{error}</p>}
    </div>
  );
}

function ResumeReportStatus({ resumeId }: { resumeId: number }) {
  const { data: status, isLoading } = useQuery({
    queryKey: ["resumeReportStatus", resumeId],
    queryFn: async () => {
      const response = await api.get(`/resumes/${resumeId}/report/latest`);
      return response.data;
    },
  });

  if (isLoading) {
    return <div className="h-3.5 w-32 rounded bg-[#EADFCF] animate-pulse" />;
  }

  if (!status?.found) {
    return (
      <div className="flex items-center gap-1.5 text-[11px] text-[#5B5F4A]">
        <AlertCircle className="h-3 w-3" />
        <span>No report generated yet — appears after the next daily run.</span>
      </div>
    );
  }

  return (
    <div className="flex flex-wrap items-center gap-3 text-[11px] text-[#5B5F4A]">
      <span className="flex items-center gap-1.5">
        <CalendarClock className="h-3 w-3" />
        Latest: {status.report_date}
      </span>
      {typeof status.job_count === "number" && (
        <span className="flex items-center gap-1.5">
          <ListChecks className="h-3 w-3" />
          {status.job_count} matched jobs
        </span>
      )}
      <a
        href={`${(process.env.NEXT_PUBLIC_API_URL || "https://ai-scraper-at0b.onrender.com/api")}/resumes/${resumeId}/report/download`}
        target="_blank"
        rel="noopener noreferrer"
        className="flex items-center gap-1 text-[#2F6F5E] font-semibold hover:underline"
      >
        <Download className="h-3 w-3" />
        Download
      </a>
    </div>
  );
}

export default function ResumesPage() {
  const queryClient = useQueryClient();
  const [isUploadOpen, setIsUploadOpen] = useState(false);
  const [isDeleteOpen, setIsDeleteOpen] = useState(false);
  const [currentResume, setCurrentResume] = useState<Resume | null>(null);
  const [expandedId, setExpandedId] = useState<number | null>(null);

  const [candidateName, setCandidateName] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [formError, setFormError] = useState("");

  const { data: resumes = [], isLoading } = useQuery<Resume[]>({
    queryKey: ["resumes"],
    queryFn: async () => {
      const response = await api.get("/resumes");
      return response.data;
    },
  });

  const uploadMutation = useMutation({
    mutationFn: async () => {
      const formData = new FormData();
      formData.append("candidate_name", candidateName.trim());
      formData.append("file", file as File);
      // api's instance default is Content-Type: application/json -- axios checks that
      // header BEFORE its own FormData handling runs, and JSON-stringifies the FormData
      // instead of sending it as multipart when it sees "application/json" already set.
      // Overriding it here (no boundary given) lets axios/the browser fill in the correct
      // multipart boundary instead.
      const response = await api.post("/resumes", formData, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      return response.data;
    },
    onSuccess: (created: Resume) => {
      queryClient.invalidateQueries({ queryKey: ["resumes"] });
      setExpandedId(created.id);
      closeUploadModal();
    },
    onError: (err: any) => {
      setFormError(extractErrorMessage(err, "Failed to upload resume."));
    },
  });

  const toggleActiveMutation = useMutation({
    mutationFn: async ({ id, is_active }: { id: number; is_active: boolean }) => {
      const response = await api.patch(`/resumes/${id}`, { is_active });
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["resumes"] });
    },
  });

  const toggleWeekendsMutation = useMutation({
    mutationFn: async ({ id, include_weekends }: { id: number; include_weekends: boolean }) => {
      const response = await api.patch(`/resumes/${id}`, { include_weekends });
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["resumes"] });
    },
  });

  const deleteMutation = useMutation({
    mutationFn: async (id: number) => {
      const response = await api.delete(`/resumes/${id}`);
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["resumes"] });
      setIsDeleteOpen(false);
    },
  });

  const openUploadModal = () => {
    setCandidateName("");
    setFile(null);
    setFormError("");
    setIsUploadOpen(true);
  };

  const closeUploadModal = () => setIsUploadOpen(false);

  const handleUpload = (e: React.FormEvent) => {
    e.preventDefault();
    setFormError("");
    if (!candidateName.trim() || !file) {
      setFormError("Candidate name and a resume file are required.");
      return;
    }
    uploadMutation.mutate();
  };

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-xl font-bold tracking-tight text-[#1E293B]">Resumes</h1>
          <p className="text-xs text-[#5B5F4A]">
            Upload a candidate resume — every active day's scrape is re-ranked for fit against it and emailed only to its own recipients.
          </p>
        </div>
        <button
          onClick={openUploadModal}
          className="btn-primary inline-flex items-center gap-1.5 text-xs py-2 px-4 font-semibold bg-[#C67C2E] text-white hover:bg-[#A9621C] rounded-xl"
        >
          <Plus className="h-4 w-4" />
          <span>Upload Resume</span>
        </button>
      </div>

      {/* Resume list */}
      <div className="space-y-3">
        {isLoading ? (
          [1, 2, 3].map((i) => (
            <div key={i} className="border border-[#EADFCF] bg-[#FFFDFC] rounded-xl p-4 animate-pulse">
              <div className="h-4 w-40 rounded bg-[#EADFCF] mb-2" />
              <div className="h-3 w-64 rounded bg-[#EADFCF]" />
            </div>
          ))
        ) : resumes.length === 0 ? (
          <div className="border border-[#EADFCF] bg-[#FFFDFC] rounded-xl p-8 text-center">
            <FileText className="h-8 w-8 text-[#5B5F4A]/50 mx-auto mb-2" />
            <p className="text-sm font-semibold text-[#1E293B]">No resumes uploaded yet</p>
            <p className="text-xs text-[#5B5F4A] mt-1">Upload one to start getting candidate-matched job leads by email.</p>
          </div>
        ) : (
          resumes.map((resume) => {
            const isExpanded = expandedId === resume.id;
            return (
              <div key={resume.id} className="border border-[#EADFCF] bg-[#FFFDFC] rounded-xl shadow-xs p-4">
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <h3 className="text-sm font-bold text-[#1E293B] truncate">{resume.candidate_name}</h3>
                      <span className={`badge ${resume.is_active ? "badge-green" : "badge-neutral"}`}>
                        {resume.is_active ? "Active" : "Paused"}
                      </span>
                      <span className="badge badge-neutral">
                        {resume.include_weekends ? "Runs Sat/Sun" : "Skips Sat/Sun"}
                      </span>
                    </div>
                    <p className="text-[11px] text-[#5B5F4A] truncate">{resume.original_filename}</p>
                    <div className="mt-2">
                      <ResumeReportStatus resumeId={resume.id} />
                    </div>
                  </div>

                  <div className="flex items-center gap-1.5 shrink-0">
                    <button
                      type="button"
                      onClick={() => toggleActiveMutation.mutate({ id: resume.id, is_active: !resume.is_active })}
                      title={resume.is_active ? "Pause matching for this resume" : "Resume matching for this resume"}
                      className={`rounded-lg p-1.5 transition ${
                        resume.is_active
                          ? "text-[#2E7D32] hover:bg-green-50"
                          : "text-[#5B5F4A] hover:bg-[#FFF9F0]"
                      }`}
                    >
                      <Power className="h-3.5 w-3.5" />
                    </button>
                    <button
                      type="button"
                      onClick={() => toggleWeekendsMutation.mutate({ id: resume.id, include_weekends: !resume.include_weekends })}
                      title={
                        resume.include_weekends
                          ? "Currently matching/emailing on Sat/Sun too -- click to skip weekends instead"
                          : "Currently skipping Sat/Sun (jobs stay unused, not marked sent) -- click to include weekends"
                      }
                      className={`rounded-lg p-1.5 transition ${
                        resume.include_weekends
                          ? "text-[#2F6F5E] hover:bg-[#2F6F5E]/10"
                          : "text-[#5B5F4A] hover:bg-[#FFF9F0]"
                      }`}
                    >
                      <CalendarOff className="h-3.5 w-3.5" />
                    </button>
                    <button
                      type="button"
                      onClick={() => { setCurrentResume(resume); setIsDeleteOpen(true); }}
                      className="text-[#C53030] hover:bg-red-50 rounded-lg p-1.5 transition"
                      title="Delete resume"
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                    </button>
                    <button
                      type="button"
                      onClick={() => setExpandedId(isExpanded ? null : resume.id)}
                      className="text-[#5B5F4A] hover:bg-[#FFF9F0] rounded-lg p-1.5 transition"
                      title="Manage recipients"
                    >
                      {isExpanded ? <ChevronUp className="h-3.5 w-3.5" /> : <ChevronDown className="h-3.5 w-3.5" />}
                    </button>
                  </div>
                </div>

                {isExpanded && <ResumeRecipients resumeId={resume.id} />}
              </div>
            );
          })
        )}
      </div>

      {/* --- UPLOAD MODAL --- */}
      {isUploadOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-500/20 p-4 backdrop-blur-xs">
          <div className="relative w-full max-w-md rounded-xl border border-[#EADFCF] bg-[#FFF9F0] p-6 shadow-2xl animate-in fade-in duration-150">
            <button onClick={closeUploadModal} className="absolute top-4 right-4 text-[#5B5F4A]/70 hover:text-[#1E293B]">
              <X className="h-4 w-4" />
            </button>
            <h3 className="text-sm font-bold uppercase tracking-wider text-[#1E293B] mb-1">Upload Resume</h3>
            <p className="text-[10px] text-[#5B5F4A] mb-6">PDF or DOCX — matched against every day's scrape, independent of the fixed-domain reports</p>

            <form onSubmit={handleUpload} className="space-y-4">
              {formError && (
                <div className="flex items-center gap-2 rounded-xl border border-red-200 bg-red-50 p-3 text-xs text-[#C53030] font-semibold animate-in fade-in">
                  <AlertCircle className="h-4 w-4 shrink-0 text-[#C53030]" />
                  <span>{formError}</span>
                </div>
              )}

              <div className="space-y-1">
                <label className="text-[10px] font-bold uppercase tracking-wider text-[#5B5F4A]">Candidate Name</label>
                <input
                  type="text"
                  required
                  placeholder="e.g. Jordan Smith"
                  value={candidateName}
                  onChange={(e) => setCandidateName(e.target.value)}
                  className="w-full rounded-xl border border-[#EADFCF] bg-[#FFFDFC] px-3 py-2 text-xs text-[#1E293B] outline-none focus:border-[#2F6F5E] focus:ring-2 focus:ring-[#2F6F5E]/10 transition"
                />
              </div>

              <div className="space-y-1">
                <label className="text-[10px] font-bold uppercase tracking-wider text-[#5B5F4A]">Resume File (.pdf or .docx)</label>
                <input
                  type="file"
                  required
                  accept=".pdf,.docx"
                  onChange={(e) => setFile(e.target.files?.[0] || null)}
                  className="w-full rounded-xl border border-[#EADFCF] bg-[#FFFDFC] px-3 py-2 text-xs text-[#1E293B] outline-none focus:border-[#2F6F5E] focus:ring-2 focus:ring-[#2F6F5E]/10 transition file:mr-3 file:rounded-lg file:border-0 file:bg-[#EADFCF] file:px-3 file:py-1 file:text-[11px] file:font-semibold"
                />
              </div>

              <div className="flex gap-2.5 justify-end pt-4 border-t border-[#EADFCF]">
                <button
                  type="button"
                  onClick={closeUploadModal}
                  className="btn-secondary py-1.5 px-3 text-[10px] font-semibold rounded-xl"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={uploadMutation.isPending}
                  className="btn-primary py-1.5 px-4 text-[10px] font-semibold bg-[#C67C2E] text-white hover:bg-[#A9621C] rounded-xl"
                >
                  {uploadMutation.isPending ? "Uploading..." : "Upload Resume"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* --- DELETE CONFIRM MODAL --- */}
      {isDeleteOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-500/20 p-4 backdrop-blur-xs">
          <div className="w-full max-w-sm rounded-xl border border-[#EADFCF] bg-[#FFF9F0] p-5 shadow-2xl animate-in fade-in duration-150">
            <h3 className="text-xs font-bold uppercase tracking-wider text-[#1E293B] mb-2">Delete resume</h3>
            <p className="text-xs text-[#5B5F4A] mb-5 leading-normal">
              Confirm deleting <span className="text-[#1E293B] font-semibold">{currentResume?.candidate_name}</span>'s resume? Its recipients and report history will be removed too, and it will stop receiving matched jobs.
            </p>
            <div className="flex gap-2 justify-end">
              <button
                onClick={() => setIsDeleteOpen(false)}
                className="btn-secondary py-1.5 px-3 text-[10px] font-semibold rounded-xl"
              >
                Cancel
              </button>
              <button
                onClick={() => currentResume && deleteMutation.mutate(currentResume.id)}
                disabled={deleteMutation.isPending}
                className="rounded-xl bg-[#C53030] px-3 py-1.5 text-[10px] font-bold text-white hover:bg-[#A92222] active:scale-95 transition cursor-pointer"
              >
                {deleteMutation.isPending ? "Deleting..." : "Delete Resume"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
