"use client";

import React, { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import {
  History,
  Terminal,
  RefreshCw,
  Clock,
  User
} from "lucide-react";
import api from "@/lib/api";

export default function ActivityPage() {
  const router = useRouter();
  const [isAdmin, setIsAdmin] = useState(false);
  const [loadingRole, setLoadingRole] = useState(true);
  const [page, setPage] = useState(1);
  const [actionFilter, setActionFilter] = useState("");

  // Role validation -- Activity Logs is admin-only, same as Operators.
  useEffect(() => {
    const userRole = localStorage.getItem("role");
    if (userRole !== "admin") {
      router.push("/dashboard");
    } else {
      setIsAdmin(true);
    }
    setLoadingRole(false);
  }, [router]);

  // Fetch Activity Logs Query
  const { data, isLoading, refetch, isFetching } = useQuery({
    queryKey: ["activityLogs", actionFilter, page],
    queryFn: async () => {
      const response = await api.get("/activity", {
        params: {
          page,
          action: actionFilter || undefined,
          limit: 20
        },
      });
      return response.data;
    },
    enabled: isAdmin,
  });

  if (loadingRole || !isAdmin) {
    return null;
  }

  const totalPages = data ? Math.ceil(data.total / data.limit) : 1;

  const formatDate = (dateStr: string) => {
    const d = new Date(dateStr);
    return d.toLocaleString("en-US", {
      month: "short",
      day: "numeric",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit"
    });
  };

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-xl font-bold tracking-tight text-[#1E293B]">System Activity Logs</h1>
          <p className="text-xs text-[#5B5F4A]">
            Audit logs of job aggregation sweeps and administrator configuration edits
          </p>
        </div>
        <button
          onClick={() => refetch()}
          disabled={isFetching}
          className="btn-secondary flex items-center gap-1.5 text-xs py-1.5 px-3 font-semibold rounded-xl"
        >
          <RefreshCw className={`h-3 w-3 ${isFetching ? "animate-spin" : ""}`} />
          <span>Refresh Logs</span>
        </button>
      </div>

      {/* Filter toolbar */}
      <div className="flex flex-col gap-4 sm:flex-row items-center justify-between border border-[#EADFCF] bg-[#FFFDFC] p-4 rounded-xl shadow-xs">
        <div className="flex items-center gap-2 text-xs text-[#5B5F4A] font-bold uppercase tracking-wider">
          <Terminal className="h-4 w-4 text-[#5B5F4A]/70" />
          <span>Audit Log Filters</span>
        </div>
        
        <select
          value={actionFilter}
          onChange={(e) => { setActionFilter(e.target.value); setPage(1); }}
          className="rounded-xl border border-[#EADFCF] bg-[#FFFDFC] px-3 py-1.5 text-xs text-[#5B5F4A] outline-none focus:border-[#2F6F5E] cursor-pointer w-full sm:w-64 font-semibold"
        >
          <option value="">All Scraper Actions</option>
          <option value="LOGIN">User Logins (LOGIN)</option>
          <option value="COMPANY_ADD">Added Targets (COMPANY_ADD)</option>
          <option value="COMPANY_EDIT">Edited Targets (COMPANY_EDIT)</option>
          <option value="COMPANY_DELETE">Deleted Targets (COMPANY_DELETE)</option>
          <option value="SCRAPE_RUN">Scraper Runs (SCRAPE_RUN)</option>
          <option value="SCRAPE_FAIL">Scraper Failures (SCRAPE_FAIL)</option>
          <option value="SETTINGS_CHANGE">Modified Settings (SETTINGS_CHANGE)</option>
          <option value="USER_CREATE">Created Operators (USER_CREATE)</option>
          <option value="USER_DELETE">Deleted Operators (USER_DELETE)</option>
        </select>
      </div>

      {/* Audit Logs Table */}
      <div className="border border-[#EADFCF] bg-[#FFFDFC] rounded-xl shadow-xs overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full border-collapse text-left text-xs text-[#1E293B]">
            <thead className="bg-[#FFF9F0] border-b border-[#EADFCF] text-[10px] font-bold uppercase tracking-wider text-[#5B5F4A]">
              <tr>
                <th className="px-6 py-3.5">Operator</th>
                <th className="px-6 py-3.5">Action Status</th>
                <th className="px-6 py-3.5">Log Messages</th>
                <th className="px-6 py-3.5">Timestamp</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#EADFCF]/60">
              {isLoading ? (
                [1, 2, 3, 4, 5].map((i) => (
                  <tr key={i} className="animate-pulse">
                    <td className="px-6 py-4"><div className="h-3.5 w-20 rounded-xl bg-[#EADFCF]"></div></td>
                    <td className="px-6 py-4"><div className="h-3.5 w-16 rounded-xl bg-[#EADFCF]"></div></td>
                    <td className="px-6 py-4"><div className="h-3.5 w-80 rounded-xl bg-[#EADFCF]"></div></td>
                    <td className="px-6 py-4"><div className="h-3.5 w-28 rounded-xl bg-[#EADFCF]"></div></td>
                  </tr>
                ))
              ) : data?.data?.length > 0 ? (
                data.data.map((log: any) => (
                  <tr key={log.id} className="hover:bg-[#FFF9F0]/60 transition-colors">
                    <td className="px-6 py-3.5 whitespace-nowrap">
                      <div className="flex items-center gap-1.5">
                        <User className="h-3.5 w-3.5 text-[#5B5F4A]/70" />
                        <span className="font-semibold text-[#1E293B]">{log.user_email}</span>
                      </div>
                    </td>
                    <td className="px-6 py-3.5 whitespace-nowrap">
                      <span className={`badge ${
                        log.action.includes("FAIL") ? "badge-red" :
                        log.action.includes("ADD") || log.action.includes("CREATE") ? "badge-green" :
                        log.action.includes("CHANGE") || log.action.includes("EDIT") ? "badge-amber" :
                        "badge-gray"
                      }`}>
                        {log.action}
                      </span>
                    </td>
                    <td className="px-6 py-3.5 text-[#1E293B] font-mono text-[10px] leading-relaxed max-w-md break-words">
                      {log.details}
                    </td>
                    <td className="px-6 py-3.5 text-[#5B5F4A] whitespace-nowrap font-mono text-[10px]">
                      <div className="flex items-center gap-1.5">
                        <Clock className="h-3.5 w-3.5 text-[#5B5F4A]/50" />
                        <span>{formatDate(log.created_at)}</span>
                      </div>
                    </td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan={4} className="px-6 py-10 text-center text-[#5B5F4A]">
                    No activity logs recorded.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>

        {/* Pagination control */}
        {totalPages > 1 && (
          <div className="flex items-center justify-between border-t border-[#EADFCF] px-6 py-3 bg-[#FFF9F0]">
            <button
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              disabled={page === 1}
              className="btn-secondary py-1 px-3 text-[10px] font-semibold rounded-xl"
            >
              Previous
            </button>
            <span className="text-[10px] font-bold text-[#5B5F4A]">
              Page {page} of {totalPages} (Total logs: {data.total})
            </span>
            <button
              onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
              disabled={page === totalPages}
              className="btn-secondary py-1 px-3 text-[10px] font-semibold rounded-xl"
            >
              Next
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
