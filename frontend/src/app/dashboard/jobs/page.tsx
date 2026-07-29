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
// earliest report that actually exists. Styled with the app's real design tokens (see
// globals.css) rather than one-off hex values, so it matches the rest of the platform.
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
        className="input w-full flex items-center justify-between cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
      >
        <span>{value ? formatDateLabel(value) : "Pick a date"}</span>
        <Calendar className="h-3.5 w-3.5" style={{ color: "var(--text-tertiary)" }} />
      </button>

      {open && (
        <div
          className="card absolute z-20 mt-1.5 w-72 p-3"
          style={{ boxShadow: "var(--shadow-lg)" }}
        >
          <div className="flex items-center justify-between mb-2">
            <button
              type="button"
              onClick={goPrev}
              disabled={!canGoPrev}
              className="btn btn-ghost btn-icon-sm disabled:opacity-30"
            >
              <ChevronLeft className="h-4 w-4" />
            </button>
            <span style={{ fontSize: "0.8125rem", fontWeight: 700, color: "var(--text-primary)" }}>
              {MONTH_NAMES[viewMonth]} {viewYear}
            </span>
            <button
              type="button"
              onClick={goNext}
              disabled={!canGoNext}
              className="btn btn-ghost btn-icon-sm disabled:opacity-30"
            >
              <ChevronRight className="h-4 w-4" />
            </button>
          </div>

          <div className="grid grid-cols-7 gap-1 mb-1">
            {WEEKDAY_LABELS.map((w) => (
              <div key={w} className="text-center text-caption" style={{ fontWeight: 700 }}>{w}</div>
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

              let style: React.CSSProperties = { fontSize: "0.6875rem", fontWeight: 600 };
              if (outOfRange) {
                style = { ...style, color: "var(--text-disabled)", cursor: "not-allowed" };
              } else if (isSelected) {
                style = { ...style, background: "var(--color-brand)", color: "#fff" };
              } else if (hasReport) {
                style = { ...style, background: "var(--blue-bg)", color: "var(--blue-text)" };
              } else {
                style = { ...style, color: "var(--text-primary)" };
              }
              if (isToday && !isSelected) {
                style = { ...style, boxShadow: "inset 0 0 0 1.5px var(--amber-text)" };
              }

              return (
                <button
                  key={iso}
                  type="button"
                  disabled={outOfRange}
                  onClick={() => { onChange(iso); setOpen(false); }}
                  style={style}
                  className={`h-7 w-7 rounded-full flex items-center justify-center mx-auto transition ${
                    outOfRange ? "" : isSelected ? "" : "hover:opacity-80 cursor-pointer"
                  }`}
                >
                  {day}
                </button>
              );
            })}
          </div>

          <div className="flex items-center gap-3 mt-3 pt-2.5 text-caption" style={{ borderTop: "1px solid var(--border-subtle)" }}>
            <span className="flex items-center gap-1.5">
              <span className="h-2 w-2 rounded-full inline-block" style={{ background: "var(--blue-bg)", boxShadow: "inset 0 0 0 1px var(--blue-border)" }} />
              Report stored
            </span>
            <span className="flex items-center gap-1.5">
              <span className="h-2 w-2 rounded-full inline-block" style={{ boxShadow: "inset 0 0 0 1.5px var(--amber-text)" }} />
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
      <div className="page-header">
        <div>
          <h1 className="page-title">Job Leads</h1>
          <p className="page-subtitle">Browse a stored day&apos;s report for a specific domain</p>
        </div>
        <button
          onClick={() => refetch()}
          disabled={isFetching || !selectedDate}
          className="btn btn-secondary btn-sm"
        >
          <RefreshCw className={`h-3 w-3 ${isFetching ? "animate-spin" : ""}`} />
          <span>Refresh</span>
        </button>
      </div>

      {/* Domain + Date selectors */}
      <div className="toolbar flex-col items-stretch sm:flex-row sm:items-center">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center w-full">
          <div className="relative w-full sm:w-64">
            <select
              value={domain}
              onChange={(e) => setDomain(e.target.value)}
              className="input appearance-none pr-8 cursor-pointer"
            >
              {DOMAIN_OPTIONS.map((opt) => (
                <option key={opt.value} value={opt.value}>{opt.label}</option>
              ))}
            </select>
            <ChevronDown className="absolute right-3 top-1/2 -translate-y-1/2 h-3.5 w-3.5 pointer-events-none" style={{ color: "var(--text-tertiary)" }} />
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
            <span className="badge badge-blue whitespace-nowrap">
              {jobsData.job_count} jobs in this report
            </span>
          )}
        </div>
      </div>
      {earliestDate && (
        <p className="text-caption -mt-4">
          {selectedDomainLabel} reports available from {formatDateLabel(earliestDate)} onward
        </p>
      )}

      {/* Leads Content Board */}
      <div className="card p-6">
        {datesLoading || jobsLoading ? (
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {[1, 2, 3, 4, 5, 6].map((i) => (
              <div key={i} className="skeleton h-40"></div>
            ))}
          </div>
        ) : dates.length === 0 ? (
          <div className="empty-state">
            <AlertCircle className="empty-state-icon" />
            <h3 className="text-title" style={{ fontSize: "0.875rem" }}>No reports stored yet for {selectedDomainLabel}</h3>
            <p className="text-caption">Check back after the next daily run, or send one from Email.</p>
          </div>
        ) : !selectedDate ? (
          <div className="empty-state">
            <AlertCircle className="empty-state-icon" />
            <h3 className="text-title" style={{ fontSize: "0.875rem" }}>Pick a date to browse {selectedDomainLabel}</h3>
            <p className="text-caption">Use the calendar above to choose a day.</p>
          </div>
        ) : jobsData && !jobsData.found ? (
          <div className="empty-state">
            <AlertCircle className="empty-state-icon" />
            <h3 className="text-title" style={{ fontSize: "0.875rem" }}>No {selectedDomainLabel} report stored for {formatDateLabel(selectedDate)}</h3>
            <p className="text-caption">Try a different date, or check back after the next daily run.</p>
          </div>
        ) : jobs.length > 0 ? (
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {jobs.map((job: any, idx: number) => (
              <div key={idx} className="card card-interactive p-4.5 flex flex-col justify-between">
                <div className="space-y-3">
                  <span className="badge badge-neutral">{job.company}</span>

                  <h3 className="text-title truncate-2" style={{ fontSize: "0.8125rem" }}>
                    {job.title}
                  </h3>

                  <div className="space-y-1.5 pt-0.5 text-caption">
                    <div className="flex items-center gap-1.5">
                      <MapPin className="h-3 w-3 shrink-0" style={{ color: "var(--text-disabled)" }} />
                      <span className="truncate">{job.location || "USA / Remote"}</span>
                    </div>
                    <div className="flex items-center gap-1.5">
                      <Award className="h-3 w-3 shrink-0" style={{ color: "var(--text-disabled)" }} />
                      <span className="truncate">{job.experience_metadata || "Experience details not specified"}</span>
                    </div>
                  </div>
                </div>

                <div className="mt-4 pt-3.5 flex items-center justify-between text-caption" style={{ borderTop: "1px solid var(--border-subtle)" }}>
                  <span className="flex items-center gap-1">
                    <Calendar className="h-3 w-3" style={{ color: "var(--text-disabled)" }} />
                    <span>{job.date_posted || "n/a"}</span>
                  </span>
                  <a
                    href={job.apply_link}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center gap-1 font-semibold transition"
                    style={{ color: "var(--color-brand)" }}
                  >
                    <span>Apply</span>
                    <ExternalLink className="h-3 w-3" />
                  </a>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="empty-state">
            <Briefcase className="empty-state-icon" />
            <h3 className="text-title" style={{ fontSize: "0.875rem" }}>No jobs in this report</h3>
            <p className="text-caption">Try a different date or domain.</p>
          </div>
        )}
      </div>
    </div>
  );
}
