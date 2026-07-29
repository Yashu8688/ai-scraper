"use client";

import React, { useState, useEffect, useRef } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  Briefcase,
  MapPin,
  Calendar,
  ExternalLink,
  RefreshCw,
  Award,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  AlertCircle,
} from "lucide-react";
import api from "@/lib/api";

const DOMAIN_OPTIONS = [
  { value: "data", label: "Data roles" },
  { value: "java", label: "Java roles" },
  { value: "dotnet", label: ".NET roles" },
  { value: "cyber", label: "Cyber roles" },
];

// Deliberately does not use `new Date(iso)` -- that parses a date-only string as UTC
// midnight, then toLocaleDateString renders it in the viewer's local timezone, which can
// shift the displayed day backward for anyone west of India (e.g. US viewers saw the
// previous day). This shows the exact stored date to everyone, regardless of where they are.
const MONTH_NAMES = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
function formatDateLabel(iso: string) {
  const [year, month, day] = iso.split("-").map(Number);
  if (!year || !month || !day) return iso;
  return `${MONTH_NAMES[month - 1]} ${day}, ${year}`;
}

// Local "today" only bounds what's pickable in the calendar (can't be a future date) -- it
// isn't used to display any stored date, so it doesn't need the same timezone care as above.
function todayLocalISO() {
  const d = new Date();
  const year = d.getFullYear();
  const month = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function pad2(n: number) {
  return String(n).padStart(2, "0");
}

function isoOf(year: number, month0: number, day: number) {
  return `${year}-${pad2(month0 + 1)}-${pad2(day)}`;
}

function monthIndex(year: number, month0: number) {
  return year * 12 + month0;
}

const WEEKDAY_LABELS = ["Su", "Mo", "Tu", "We", "Th", "Fr", "Sa"];

// A native <input type="date"> can't color individual days or block navigation to months
// with no data at all -- this is a small self-contained calendar built specifically so
// "has a stored report" days are visually distinct and you can't scroll back before the
// earliest report that actually exists.
function ReportCalendar({
  value,
  onChange,
  minDate,
  maxDate,
  availableDates,
  disabled,
}: {
  value: string;
  onChange: (iso: string) => void;
  minDate?: string;
  maxDate: string;
  availableDates: Set<string>;
  disabled?: boolean;
}) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [open, setOpen] = useState(false);

  const anchor = value || minDate || maxDate;
  const [anchorYear, anchorMonth] = anchor.split("-").map(Number);
  const [viewYear, setViewYear] = useState(anchorYear);
  const [viewMonth, setViewMonth] = useState(anchorMonth - 1);

  // Jump the visible month back to the selected date whenever it changes from outside
  // (e.g. switching domain resets to that domain's latest date).
  useEffect(() => {
    const [y, m] = anchor.split("-").map(Number);
    setViewYear(y);
    setViewMonth(m - 1);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [anchor]);

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const [maxY, maxM] = maxDate.split("-").map(Number);
  const maxIdx = monthIndex(maxY, maxM - 1);
  const minIdx = minDate ? (() => { const [y, m] = minDate.split("-").map(Number); return monthIndex(y, m - 1); })() : -Infinity;

  const viewIdx = monthIndex(viewYear, viewMonth);
  const canGoPrev = viewIdx > minIdx;
  const canGoNext = viewIdx < maxIdx;

  const goPrev = () => {
    if (!canGoPrev) return;
    const idx = viewIdx - 1;
    setViewYear(Math.floor(idx / 12));
    setViewMonth(((idx % 12) + 12) % 12);
  };
  const goNext = () => {
    if (!canGoNext) return;
    const idx = viewIdx + 1;
    setViewYear(Math.floor(idx / 12));
    setViewMonth(((idx % 12) + 12) % 12);
  };

  const daysInMonth = new Date(viewYear, viewMonth + 1, 0).getDate();
  const firstWeekday = new Date(viewYear, viewMonth, 1).getDay();
  const cells: (number | null)[] = [
    ...Array(firstWeekday).fill(null),
    ...Array.from({ length: daysInMonth }, (_, i) => i + 1),
  ];

  const today = todayLocalISO();

  return (
    <div ref={containerRef} className="relative w-full sm:w-64">
      <button
        type="button"
        onClick={() => !disabled && setOpen((o) => !o)}
        disabled={disabled}
        className="w-full flex items-center justify-between rounded-xl border border-[#EADFCF] bg-[#FFFDFC] px-3 py-2 text-xs text-[#1E293B] outline-none focus:border-[#2F6F5E] cursor-pointer font-semibold disabled:opacity-50 disabled:cursor-not-allowed"
      >
        <span>{value ? formatDateLabel(value) : "Pick a date"}</span>
        <Calendar className="h-3.5 w-3.5 text-[#5B5F4A]" />
      </button>

      {open && (
        <div className="absolute z-20 mt-1.5 w-72 rounded-xl border border-[#EADFCF] bg-[#FFFDFC] shadow-lg p-3">
          <div className="flex items-center justify-between mb-2">
            <button
              type="button"
              onClick={goPrev}
              disabled={!canGoPrev}
              className="rounded-lg p-1 text-[#5B5F4A] hover:bg-[#FFF9F0] disabled:opacity-30 disabled:cursor-not-allowed transition"
            >
              <ChevronLeft className="h-4 w-4" />
            </button>
            <span className="text-xs font-bold text-[#1E293B]">
              {MONTH_NAMES[viewMonth]} {viewYear}
            </span>
            <button
              type="button"
              onClick={goNext}
              disabled={!canGoNext}
              className="rounded-lg p-1 text-[#5B5F4A] hover:bg-[#FFF9F0] disabled:opacity-30 disabled:cursor-not-allowed transition"
            >
              <ChevronRight className="h-4 w-4" />
            </button>
          </div>

          <div className="grid grid-cols-7 gap-1 mb-1">
            {WEEKDAY_LABELS.map((w) => (
              <div key={w} className="text-center text-[9px] font-bold text-[#5B5F4A]/70">{w}</div>
            ))}
          </div>

          <div className="grid grid-cols-7 gap-1">
            {cells.map((day, idx) => {
              if (day === null) return <div key={`blank-${idx}`} />;
              const iso = isoOf(viewYear, viewMonth, day);
              const outOfRange = iso > maxDate || (minDate ? iso < minDate : false);
              const hasReport = availableDates.has(iso);
              const isSelected = iso === value;
              const isToday = iso === today;

              return (
                <button
                  key={iso}
                  type="button"
                  disabled={outOfRange}
                  onClick={() => { onChange(iso); setOpen(false); }}
                  className={[
                    "h-7 w-7 rounded-full text-[10px] font-semibold transition flex items-center justify-center mx-auto",
                    outOfRange
                      ? "text-[#5B5F4A]/25 cursor-not-allowed"
                      : isSelected
                      ? "bg-[#2F6F5E] text-white"
                      : hasReport
                      ? "bg-[#2F6F5E]/15 text-[#2F6F5E] hover:bg-[#2F6F5E]/25 cursor-pointer"
                      : "text-[#1E293B] hover:bg-[#FFF9F0] cursor-pointer",
                    isToday && !isSelected ? "ring-1 ring-[#C67C2E]" : "",
                  ].join(" ")}
                >
                  {day}
                </button>
              );
            })}
          </div>

          <div className="flex items-center gap-3 mt-3 pt-2.5 border-t border-[#EADFCF] text-[9px] text-[#5B5F4A]">
            <span className="flex items-center gap-1">
              <span className="h-2 w-2 rounded-full bg-[#2F6F5E]/25 inline-block" />
              Report stored
            </span>
            <span className="flex items-center gap-1">
              <span className="h-2 w-2 rounded-full ring-1 ring-[#C67C2E] inline-block" />
              Today
            </span>
          </div>
        </div>
      )}
    </div>
  );
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

  const dates: string[] = datesData?.dates || []; // newest first, per the API
  const earliestDate = dates.length > 0 ? dates[dates.length - 1] : undefined;
  const availableDates = new Set(dates);

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
      <div className="flex flex-col gap-2 border border-[#EADFCF] bg-[#FFFDFC] p-4 rounded-xl shadow-xs">
        <div className="flex flex-col gap-4 sm:flex-row items-center">
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

          <ReportCalendar
            value={selectedDate}
            onChange={setSelectedDate}
            minDate={earliestDate}
            maxDate={todayLocalISO()}
            availableDates={availableDates}
            disabled={datesLoading || dates.length === 0}
          />

          {jobsData?.found && typeof jobsData.job_count === "number" && (
            <span className="text-[11px] font-semibold text-[#5B5F4A] whitespace-nowrap">
              {jobsData.job_count} jobs in this report
            </span>
          )}
        </div>

        {earliestDate && (
          <p className="text-[10px] text-[#5B5F4A] pl-0.5">
            {selectedDomainLabel} reports available from {formatDateLabel(earliestDate)} onward
          </p>
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
        ) : !selectedDate ? (
          <div className="flex flex-col items-center justify-center py-16 text-[#5B5F4A]">
            <AlertCircle className="h-10 w-10 text-[#EADFCF] mb-2" />
            <h3 className="text-sm font-bold text-[#1E293B]">Pick a date to browse {selectedDomainLabel}</h3>
            <p className="text-[11px] mt-0.5">Use the calendar above to choose a day.</p>
          </div>
        ) : jobsData && !jobsData.found ? (
          <div className="flex flex-col items-center justify-center py-16 text-[#5B5F4A]">
            <AlertCircle className="h-10 w-10 text-[#EADFCF] mb-2" />
            <h3 className="text-sm font-bold text-[#1E293B]">No {selectedDomainLabel} report stored for {formatDateLabel(selectedDate)}</h3>
            <p className="text-[11px] mt-0.5">Try a different date, or check back after the next daily run.</p>
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
