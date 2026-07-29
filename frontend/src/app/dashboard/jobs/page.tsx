"use client";

import React, { useState, useEffect } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  Briefcase,
  MapPin,
  Calendar,
  ExternalLink,
  RefreshCw,
  Award,
  ChevronDown,
  AlertCircle,
} from "lucide-react";
import api from "@/lib/api";

const DOMAIN_OPTIONS = [
  { value: "data", label: "Data roles" },
  { value: "java", label: "Java roles" },
  { value: "dotnet", label: ".NET roles" },
  { value: "cyber", label: "Cyber roles" },
];

function formatDateLabel(iso: string) {
  const d = new Date(iso);
  if (isNaN(d.getTime())) return iso;
  return d.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
}

export default function JobsPage() {
  const [domain, setDomain] = useState("cyber");
  const [selectedDate, setSelectedDate] = useState("");

  const { data: datesData, isLoading: datesLoading } = useQuery({
    queryKey: ["domainReportDates", domain],
    queryFn: async () => {
      const response = await api.get("/domain-reports/dates", { params: { domain } });
      return response.data;
    },
  });

  const dates: string[] = datesData?.dates || [];

  // Default to the most recent available date whenever the domain (or its date list) changes.
  useEffect(() => {
    if (dates.length > 0 && !dates.includes(selectedDate)) {
      setSelectedDate(dates[0]);
    } else if (dates.length === 0) {
      setSelectedDate("");
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [domain, datesData]);

  const { data: jobsData, isLoading: jobsLoading, refetch, isFetching } = useQuery({
    queryKey: ["domainReportJobs", domain, selectedDate],
    queryFn: async () => {
      const response = await api.get("/domain-reports/by-date", { params: { domain, date: selectedDate } });
      return response.data;
    },
    enabled: !!selectedDate,
  });

  const jobs: any[] = jobsData?.jobs || [];
  const selectedDomainLabel = DOMAIN_OPTIONS.find((d) => d.value === domain)?.label;

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-xl font-bold tracking-tight text-[#1E293B]">Job Leads</h1>
          <p className="text-xs text-[#5B5F4A]">
            Browse a stored day's report for a specific domain
          </p>
        </div>
        <button
          onClick={() => refetch()}
          disabled={isFetching || !selectedDate}
          className="btn-secondary flex items-center gap-1.5 text-xs py-1.5 px-3 font-semibold rounded-xl"
        >
          <RefreshCw className={`h-3 w-3 ${isFetching ? "animate-spin" : ""}`} />
          <span>Refresh</span>
        </button>
      </div>

      {/* Domain + Date selectors */}
      <div className="flex flex-col gap-4 sm:flex-row items-center border border-[#EADFCF] bg-[#FFFDFC] p-4 rounded-xl shadow-xs">
        <div className="relative w-full sm:w-64">
          <select
            value={domain}
            onChange={(e) => setDomain(e.target.value)}
            className="w-full appearance-none rounded-xl border border-[#EADFCF] bg-[#FFFDFC] pl-3 pr-8.5 py-2 text-xs text-[#1E293B] outline-none focus:border-[#2F6F5E] cursor-pointer font-semibold"
          >
            {DOMAIN_OPTIONS.map((opt) => (
              <option key={opt.value} value={opt.value}>{opt.label}</option>
            ))}
          </select>
          <ChevronDown className="absolute right-3.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-[#5B5F4A] pointer-events-none" />
        </div>

        <div className="relative w-full sm:w-64">
          <select
            value={selectedDate}
            onChange={(e) => setSelectedDate(e.target.value)}
            disabled={datesLoading || dates.length === 0}
            className="w-full appearance-none rounded-xl border border-[#EADFCF] bg-[#FFFDFC] pl-3 pr-8.5 py-2 text-xs text-[#1E293B] outline-none focus:border-[#2F6F5E] cursor-pointer font-semibold disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {dates.length === 0 ? (
              <option value="">No stored reports yet</option>
            ) : (
              dates.map((d) => (
                <option key={d} value={d}>{formatDateLabel(d)}</option>
              ))
            )}
          </select>
          <ChevronDown className="absolute right-3.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-[#5B5F4A] pointer-events-none" />
        </div>

        {jobsData?.found && typeof jobsData.job_count === "number" && (
          <span className="text-[11px] font-semibold text-[#5B5F4A] whitespace-nowrap">
            {jobsData.job_count} jobs in this report
          </span>
        )}
      </div>

      {/* Leads Content Board */}
      <div className="border border-[#EADFCF] bg-[#FFFDFC] p-6 rounded-xl shadow-xs">
        {datesLoading || jobsLoading ? (
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 animate-pulse">
            {[1, 2, 3, 4, 5, 6].map((i) => (
              <div key={i} className="h-40 rounded-xl bg-[#FFF9F0] border border-[#EADFCF]"></div>
            ))}
          </div>
        ) : dates.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-16 text-[#5B5F4A]">
            <AlertCircle className="h-10 w-10 text-[#EADFCF] mb-2" />
            <h3 className="text-sm font-bold text-[#1E293B]">No reports stored yet for {selectedDomainLabel}</h3>
            <p className="text-[11px] mt-0.5">Check back after the next daily run, or send one from Email.</p>
          </div>
        ) : jobs.length > 0 ? (
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {jobs.map((job: any, idx: number) => (
              <div key={idx} className="flex flex-col justify-between rounded-xl border border-[#EADFCF] bg-[#FFFDFC] p-4.5 hover:border-[#D1C4B2] hover:shadow-sm transition duration-150">
                <div className="space-y-3">
                  <div className="flex items-center">
                    <span className="badge badge-gray text-[9px] font-bold uppercase tracking-wide px-2 py-0.5 border border-[#EADFCF] bg-[#FFF9F0] text-[#5B5F4A]">
                      {job.company}
                    </span>
                  </div>

                  <h3 className="text-sm font-bold text-[#1E293B] leading-snug line-clamp-2">
                    {job.title}
                  </h3>

                  <div className="space-y-1.5 pt-0.5 text-[10px] text-[#5B5F4A] font-semibold">
                    <div className="flex items-center gap-1.5">
                      <MapPin className="h-3 w-3 text-[#5B5F4A]/60 shrink-0" />
                      <span className="truncate">{job.location || "USA / Remote"}</span>
                    </div>
                    <div className="flex items-center gap-1.5">
                      <Award className="h-3 w-3 text-[#5B5F4A]/60 shrink-0" />
                      <span className="truncate">{job.experience_metadata || "Experience details not specified"}</span>
                    </div>
                  </div>
                </div>

                <div className="mt-4 pt-3.5 border-t border-[#FFF9F0] flex items-center justify-between text-[10px] font-bold text-[#5B5F4A]">
                  <span className="flex items-center gap-1">
                    <Calendar className="h-3 w-3 text-[#5B5F4A]/50" />
                    <span>{job.date_posted || "n/a"}</span>
                  </span>
                  <a
                    href={job.apply_link}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center gap-1 text-[#C67C2E] hover:text-[#A9621C] transition"
                  >
                    <span>Apply</span>
                    <ExternalLink className="h-3 w-3" />
                  </a>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="flex flex-col items-center justify-center py-16 text-[#5B5F4A]">
            <Briefcase className="h-10 w-10 text-[#EADFCF] mb-2" />
            <h3 className="text-sm font-bold text-[#1E293B]">No jobs in this report</h3>
            <p className="text-[11px] mt-0.5">Try a different date or domain.</p>
          </div>
        )}
      </div>
    </div>
  );
}
