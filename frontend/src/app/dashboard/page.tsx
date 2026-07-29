"use client";

import React from "react";
import { useQuery } from "@tanstack/react-query";
import {
  Building2,
  ChevronRight,
  RefreshCw,
  TrendingUp,
  Activity
} from "lucide-react";
import api from "@/lib/api";

export default function DashboardOverview() {
  const { data, isLoading, isError, refetch, isFetching } = useQuery({
    queryKey: ["dashboardStats"],
    queryFn: async () => {
      const response = await api.get("/dashboard/stats");
      return response.data;
    },
    refetchInterval: 45000,
  });

  const formatDate = (dateStr: string) => {
    const d = new Date(dateStr);
    return d.toLocaleString("en-US", {
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  };

  if (isLoading) {
    return (
      <div className="space-y-6 animate-pulse">
        <div className="flex justify-between items-center">
          <div className="space-y-1.5">
            <div className="h-6 w-36 rounded-xl bg-[#EADFCF]"></div>
            <div className="h-3 w-52 rounded-xl bg-[#EADFCF]"></div>
          </div>
          <div className="h-8 w-24 rounded-xl bg-[#EADFCF]"></div>
        </div>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {[1, 2, 3, 4].map((i) => (
            <div key={i} className="h-24 rounded-xl bg-[#FFFDFC] border border-[#EADFCF]"></div>
          ))}
        </div>
        <div className="grid gap-4 lg:grid-cols-3">
          <div className="lg:col-span-2 h-80 rounded-xl bg-[#FFFDFC] border border-[#EADFCF]"></div>
          <div className="h-80 rounded-xl bg-[#FFFDFC] border border-[#EADFCF]"></div>
        </div>
      </div>
    );
  }

  if (isError) {
    return (
      <div className="rounded-xl border border-red-200 bg-red-50 p-6 text-center text-red-750">
        <h3 className="text-sm font-semibold">Failed to load system metrics</h3>
        <p className="mt-1 text-xs text-[#5B5F4A]">Verify that the FastAPI backend server is running on port 8000.</p>
        <button
          onClick={() => refetch()}
          className="mt-4 rounded-xl bg-[#C67C2E] px-4.5 py-1.5 text-xs font-semibold text-white hover:bg-[#A9621C] transition cursor-pointer"
        >
          Retry Connection
        </button>
      </div>
    );
  }

  // Chart configuration
  const trends = data?.trends || [];
  const chartHeight = 110;
  const chartWidth = 500;
  const maxVal = Math.max(...trends.map((t: any) => t.jobs), 8);
  
  const points = trends.map((t: any, idx: number) => {
    const x = (idx / (trends.length - 1)) * chartWidth;
    const y = chartHeight - (t.jobs / maxVal) * chartHeight;
    return `${x},${y}`;
  }).join(" ");

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-xl font-bold tracking-tight text-[#1E293B]">Recruitment Overview</h1>
          <p className="text-xs text-[#5B5F4A]">
            System status monitoring automated job sweeps
          </p>
        </div>
        <button
          onClick={() => refetch()}
          disabled={isFetching}
          className="btn-secondary flex items-center gap-1.5 text-xs py-1.5 px-3 font-semibold"
        >
          <RefreshCw className={`h-3 w-3 ${isFetching ? "animate-spin" : ""}`} />
          <span>Refresh stats</span>
        </button>
      </div>

      {/* KPI metrics */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {/* Companies */}
        <div className="border border-[#EADFCF] bg-[#FFFDFC] p-4 rounded-xl shadow-xs flex flex-col justify-between">
          <div className="flex items-center justify-between">
            <span className="text-[10px] font-bold uppercase tracking-wider text-[#5B5F4A]">Companies</span>
            <Building2 className="h-4.5 w-4.5 text-[#2F6F5E]" />
          </div>
          <div className="mt-2.5">
            <span className="text-2xl font-bold text-[#1E293B] tracking-tight">{data.total_companies}</span>
          </div>
        </div>
      </div>

      {/* Analytics Chart & Activity Panel */}
      <div className="grid gap-4 lg:grid-cols-3">
        {/* SVG Scrape Trend Chart */}
        <div className="lg:col-span-2 border border-[#EADFCF] bg-[#FFFDFC] p-5 rounded-xl shadow-xs flex flex-col justify-between">
          <div>
            <div className="flex items-center gap-1.5">
              <TrendingUp className="h-3.5 w-3.5 text-[#2F6F5E]" />
              <h3 className="text-xs font-bold uppercase tracking-wider text-[#1E293B]">Job lead aggregation trend</h3>
            </div>
            <p className="text-[10px] text-[#5B5F4A] mt-0.5">Daily aggregated job listings</p>
          </div>

          <div className="mt-6 flex-1 flex items-end justify-center">
            {trends.length > 0 ? (
              <div className="w-full">
                <svg viewBox={`0 0 ${chartWidth} ${chartHeight}`} className="w-full overflow-visible">
                  {/* Grid Lines */}
                  <line x1="0" y1="0" x2={chartWidth} y2="0" stroke="#FFF9F0" strokeDasharray="3,3" />
                  <line x1="0" y1={chartHeight / 2} x2={chartWidth} y2={chartHeight / 2} stroke="#FFF9F0" strokeDasharray="3,3" />
                  <line x1="0" y1={chartHeight} x2={chartWidth} y2={chartHeight} stroke="#EADFCF" />
                  
                  {/* Line Graph (Forest Green) */}
                  <polyline
                    fill="none"
                    stroke="#2F6F5E"
                    strokeWidth="2"
                    points={points}
                  />

                  {/* Nodes */}
                  {trends.map((t: any, idx: number) => {
                    const x = (idx / (trends.length - 1)) * chartWidth;
                    const y = chartHeight - (t.jobs / maxVal) * chartHeight;
                    return (
                      <g key={idx} className="group cursor-pointer">
                        <circle
                          cx={x}
                          cy={y}
                          r="4"
                          className="fill-white stroke-[#2F6F5E] stroke-2 hover:r-5 transition-all"
                        />
                        <text
                          x={x}
                          y={y - 8}
                          textAnchor="middle"
                          className="hidden group-hover:block fill-[#1E293B] text-[9px] font-bold"
                        >
                          {t.jobs}
                        </text>
                      </g>
                    );
                  })}
                </svg>
                
                {/* Chart Label */}
                <div className="mt-3 flex justify-between px-1 text-[9px] font-bold text-[#5B5F4A]">
                  {trends.map((t: any, idx: number) => (
                    <span key={idx}>{t.date}</span>
                  ))}
                </div>
              </div>
            ) : (
              <span className="text-xs text-[#5B5F4A]">No weekly lead metrics identified.</span>
            )}
          </div>
        </div>

        {/* Audit Log Timeline */}
        <div className="border border-[#EADFCF] bg-[#FFFDFC] p-5 rounded-xl shadow-xs flex flex-col justify-between">
          <div>
            <div className="flex items-center gap-1.5">
              <Activity className="h-3.5 w-3.5 text-[#2F6F5E]" />
              <h3 className="text-xs font-bold uppercase tracking-wider text-[#1E293B]">Operational History Logs</h3>
            </div>
            <p className="text-[10px] text-[#5B5F4A] mt-0.5">Scraper actions feed</p>
          </div>

          <div className="mt-4 flex-1 space-y-3">
            {data.recent_activity?.length > 0 ? (
              data.recent_activity.map((log: any) => (
                <div key={log.id} className="flex items-start gap-2 border-b border-[#FFF9F0] pb-2.5 last:border-0 last:pb-0">
                  <div className="mt-0.5 rounded-lg bg-[#FFF9F0] border border-[#EADFCF] p-1 text-[#5B5F4A] shrink-0">
                    <ChevronRight className="h-2.5 w-2.5" />
                  </div>
                  <div className="min-w-0 flex-1">
                    <p className="text-xs font-semibold text-[#1E293B] truncate leading-tight">{log.details || log.action}</p>
                    <div className="mt-1 flex items-center justify-between text-[9px] font-mono text-[#5B5F4A]">
                      <span>{log.user_email}</span>
                      <span>{formatDate(log.created_at)}</span>
                    </div>
                  </div>
                </div>
              ))
            ) : (
              <div className="flex h-full items-center justify-center py-10">
                <span className="text-[10px] text-[#5B5F4A]">No operational history logs.</span>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
