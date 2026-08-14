"use client";

import React, { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { 
  Building2, 
  Search, 
  Plus, 
  Edit2, 
  Trash2, 
  Play, 
  X, 
  Check, 
  Loader2, 
  AlertCircle,
  ExternalLink,
  ChevronDown
} from "lucide-react";
import api from "@/lib/api";

export default function CompaniesPage() {
  const queryClient = useQueryClient();
  const [search, setSearch] = useState("");
  const [atsFilter, setAtsFilter] = useState("");
  const [page, setPage] = useState(1);
  
  // Modal states
  const [isAddOpen, setIsAddOpen] = useState(false);
  const [isEditOpen, setIsEditOpen] = useState(false);
  const [isDeleteOpen, setIsDeleteOpen] = useState(false);
  const [isScrapeResultOpen, setIsScrapeResultOpen] = useState(false);
  const [currentCompany, setCurrentCompany] = useState<any>(null);
  
  // Form fields
  const [name, setName] = useState("");
  const [ats, setAts] = useState("greenhouse");
  const [token, setToken] = useState("");
  const [careersUrl, setCareersUrl] = useState("");
  const [formError, setFormError] = useState("");
  
  // Scraper progress spinner state
  const [scrapeLoading, setScrapeLoading] = useState(false);
  const [scrapeResult, setScrapeResult] = useState<any>(null);

  // Fetch Companies Query
  const { data, isLoading } = useQuery({
    queryKey: ["companies", search, atsFilter, page],
    queryFn: async () => {
      const response = await api.get("/companies", {
        params: { page, search: search || undefined, ats: atsFilter || undefined, limit: 12 },
      });
      return response.data;
    },
  });

  const totalPages = data ? Math.ceil(data.total / data.limit) : 1;

  // Mutations
  const createMutation = useMutation({
    mutationFn: async (newCompany: any) => {
      const response = await api.post("/companies", newCompany);
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["companies"] });
      queryClient.invalidateQueries({ queryKey: ["dashboardStats"] });
      closeAddModal();
    },
    onError: (err: any) => {
      setFormError(err.response?.data?.detail || "Failed to create company configuration.");
    }
  });

  const updateMutation = useMutation({
    mutationFn: async ({ id, updatedData }: { id: number; updatedData: any }) => {
      const response = await api.put(`/companies/${id}`, updatedData);
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["companies"] });
      closeEditModal();
    },
    onError: (err: any) => {
      setFormError(err.response?.data?.detail || "Failed to update company configuration.");
    }
  });

  const deleteMutation = useMutation({
    mutationFn: async (id: number) => {
      const response = await api.delete(`/companies/${id}`);
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["companies"] });
      queryClient.invalidateQueries({ queryKey: ["dashboardStats"] });
      setIsDeleteOpen(false);
    }
  });

  const scrapeMutation = useMutation({
    mutationFn: async (id: number) => {
      setScrapeLoading(true);
      const response = await api.post(`/companies/${id}/scrape`);
      return response.data;
    },
    onSuccess: (data) => {
      setScrapeResult(data);
      setIsScrapeResultOpen(true);
      queryClient.invalidateQueries({ queryKey: ["jobs"] });
      queryClient.invalidateQueries({ queryKey: ["dashboardStats"] });
    },
    onError: (err: any) => {
      alert(err.response?.data?.detail || "Failed to scrape company.");
    },
    onSettled: () => {
      setScrapeLoading(false);
    }
  });

  // Modal actions
  const openAddModal = () => {
    setName("");
    setAts("greenhouse");
    setToken("");
    setCareersUrl("");
    setFormError("");
    setIsAddOpen(true);
  };

  const closeAddModal = () => {
    setIsAddOpen(false);
  };

  const openEditModal = (company: any) => {
    setCurrentCompany(company);
    setName(company.name);
    setAts(company.ats);
    setToken(company.token || "");
    setCareersUrl(company.careers_url || "");
    setFormError("");
    setIsEditOpen(true);
  };

  const closeEditModal = () => {
    setIsEditOpen(false);
    setCurrentCompany(null);
  };

  const openDeleteModal = (company: any) => {
    setCurrentCompany(company);
    setIsDeleteOpen(true);
  };

  const handleCreate = (e: React.FormEvent, runScrapeAfterSave: boolean = false) => {
    e.preventDefault();
    setFormError("");

    if (!name || !ats) {
      setFormError("Company name and ATS type are required.");
      return;
    }

    if (ats !== "playwright" && ats !== "all" && !token) {
      setFormError(`ATS token slug is required for ${ats}.`);
      return;
    }

    if (ats === "all" && !token && !careersUrl) {
      setFormError("Either ATS token slug or Careers Page URL is required for 'All'.");
      return;
    }

    const payload = {
      name,
      ats,
      token: (ats === "playwright" || (ats === "all" && !token)) ? null : token,
      careers_url: careersUrl
    };

    if (runScrapeAfterSave) {
      createMutation.mutate(payload, {
        onSuccess: (savedCompany) => {
          scrapeMutation.mutate(savedCompany.id);
        }
      });
    } else {
      createMutation.mutate(payload);
    }
  };

  const handleUpdate = (e: React.FormEvent) => {
    e.preventDefault();
    setFormError("");

    if (!name || !ats) {
      setFormError("Company name and ATS type are required.");
      return;
    }

    if (ats !== "playwright" && ats !== "all" && !token) {
      setFormError(`ATS token slug is required for ${ats}.`);
      return;
    }

    if (ats === "all" && !token && !careersUrl) {
      setFormError("Either ATS token slug or Careers Page URL is required for 'All'.");
      return;
    }

    const payload = {
      name,
      ats,
      token: (ats === "playwright" || (ats === "all" && !token)) ? null : token,
      careers_url: careersUrl
    };

    updateMutation.mutate({ id: currentCompany.id, updatedData: payload });
  };

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-xl font-bold tracking-tight text-[#1E293B]">Companies Directory</h1>
          <p className="text-xs text-[#5B5F4A]">
            Manage integration properties and targets for automated scraper loops
          </p>
        </div>
        <button
          onClick={openAddModal}
          className="btn-primary inline-flex items-center gap-1.5 text-xs py-2 px-4 font-semibold bg-[#C67C2E] text-white hover:bg-[#A9621C] rounded-xl"
        >
          <Plus className="h-4 w-4" />
          <span>Add Company</span>
        </button>
      </div>

      {/* Filter and Search toolbar */}
      <div className="flex flex-col gap-4 sm:flex-row items-center justify-between border border-[#EADFCF] bg-[#FFFDFC] p-4 rounded-xl shadow-xs">
        {/* Search */}
        <div className="relative w-full sm:w-80">
          <Search className="absolute top-1/2 left-3 h-3.5 w-3.5 -translate-y-1/2 text-[#5B5F4A]/75" />
          <input
            type="text"
            placeholder="Search company or token..."
            value={search}
            onChange={(e) => { setSearch(e.target.value); setPage(1); }}
            className="w-full rounded-xl border border-[#EADFCF] bg-[#FFFDFC] px-8 py-1.5 text-xs text-[#1E293B] placeholder-gray-400 transition focus:border-[#2F6F5E] focus:ring-2 focus:ring-[#2F6F5E]/10 outline-none"
          />
        </div>

        {/* ATS Filter */}
        <div className="relative w-full sm:w-auto">
          <select
            value={atsFilter}
            onChange={(e) => { setAtsFilter(e.target.value); setPage(1); }}
            className="w-full sm:w-auto appearance-none rounded-xl border border-[#EADFCF] bg-[#FFFDFC] pl-3 pr-8.5 py-1.5 text-xs text-[#5B5F4A] outline-none focus:border-[#2F6F5E] cursor-pointer font-semibold"
          >
            <option value="">All Company Types</option>
            <option value="greenhouse">Greenhouse API</option>
            <option value="lever">Lever API</option>
            <option value="ashby">Ashby API</option>
            <option value="workday">Workday API</option>
            <option value="playwright">Playwright Custom Crawler</option>
          </select>
          <ChevronDown className="absolute right-3.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-[#5B5F4A] pointer-events-none" />
        </div>
      </div>

      {/* Grid Table List */}
      <div className="border border-[#EADFCF] bg-[#FFFDFC] rounded-xl shadow-xs overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full border-collapse text-left text-xs text-[#1E293B]">
            <thead className="bg-[#FFF9F0] border-b border-[#EADFCF] text-[10px] font-bold uppercase tracking-wider text-[#5B5F4A]">
              <tr>
                <th className="px-6 py-3.5">Company Name</th>
                <th className="px-6 py-3.5">ATS Provider</th>
                <th className="px-6 py-3.5">Token Slug</th>
                <th className="px-6 py-3.5">Careers Board</th>
                <th className="px-6 py-3.5 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#EADFCF]/60">
              {isLoading ? (
                [1, 2, 3, 4, 5].map((i) => (
                  <tr key={i} className="animate-pulse">
                    <td className="px-6 py-4"><div className="h-3.5 w-24 rounded-xl bg-[#EADFCF]"></div></td>
                    <td className="px-6 py-4"><div className="h-3.5 w-16 rounded-xl bg-[#EADFCF]"></div></td>
                    <td className="px-6 py-4"><div className="h-3.5 w-16 rounded-xl bg-[#EADFCF]"></div></td>
                    <td className="px-6 py-4"><div className="h-3.5 w-32 rounded-xl bg-[#EADFCF]"></div></td>
                    <td className="px-6 py-4 text-right"><div className="h-7 w-20 ml-auto rounded-xl bg-[#EADFCF]"></div></td>
                  </tr>
                ))
              ) : data?.data?.length > 0 ? (
                data.data.map((company: any) => (
                  <tr key={company.id} className="hover:bg-[#FFF9F0]/60 transition-colors">
                    <td className="px-6 py-3.5 font-bold text-[#1E293B]">
                      {company.name}
                    </td>
                    <td className="px-6 py-3.5">
                      <span className={`badge ${
                        company.ats === "greenhouse" ? "badge-green" :
                        company.ats === "lever" ? "badge-blue" :
                        company.ats === "ashby" ? "badge-purple" :
                        "badge-amber"
                      }`}>
                        {company.ats}
                      </span>
                    </td>
                    <td className="px-6 py-3.5 font-mono text-[10px] text-[#5B5F4A]">
                      {company.token || "n/a"}
                    </td>
                    <td className="px-6 py-3.5 truncate max-w-xs text-[#5B5F4A] font-mono text-[10px]">
                      {company.careers_url ? (
                        <a href={company.careers_url} target="_blank" className="inline-flex items-center gap-1 text-[#2F6F5E] hover:underline transition">
                          <span>Link</span>
                          <ExternalLink className="h-3 w-3" />
                        </a>
                      ) : (
                        <span className="text-[#5B5F4A]/50">none</span>
                      )}
                    </td>
                    <td className="px-6 py-3.5 text-right space-x-1 whitespace-nowrap">
                      {/* Scrape Target */}
                      <button
                        onClick={() => scrapeMutation.mutate(company.id)}
                        title="Scrape target board now"
                        className="inline-flex h-7 w-7 items-center justify-center rounded-xl border border-[#EADFCF] bg-[#FFFDFC] text-[#5B5F4A] hover:bg-[#2F6F5E]/5 hover:text-[#2F6F5E] hover:border-[#2F6F5E]/20 transition active:scale-95 cursor-pointer"
                      >
                        <Play className="h-3 w-3" />
                      </button>

                      {/* Edit Target */}
                      <button
                        onClick={() => openEditModal(company)}
                        title="Edit configurations"
                        className="inline-flex h-7 w-7 items-center justify-center rounded-xl border border-[#EADFCF] bg-[#FFFDFC] text-[#5B5F4A] hover:bg-[#FFF9F0] hover:text-[#1E293B] hover:border-[#D1C4B2] transition active:scale-95 cursor-pointer"
                      >
                        <Edit2 className="h-3 w-3" />
                      </button>

                      {/* Delete Target */}
                      <button
                        onClick={() => openDeleteModal(company)}
                        title="Delete target config"
                        className="inline-flex h-7 w-7 items-center justify-center rounded-xl border border-[#EADFCF] bg-[#FFFDFC] text-[#5B5F4A] hover:bg-red-50 hover:text-[#C53030] hover:border-red-200 transition active:scale-95 cursor-pointer"
                      >
                        <Trash2 className="h-3 w-3" />
                      </button>
                    </td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan={5} className="px-6 py-10 text-center text-[#5B5F4A]">
                    No scraper target companies registered.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>

        {/* Pagination bar */}
        {totalPages > 1 && (
          <div className="flex items-center justify-between border-t border-[#EADFCF] px-6 py-3 bg-[#FFF9F0]">
            <button
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              disabled={page === 1}
              className="btn-secondary py-1 px-3 text-[10px] font-semibold"
            >
              Previous
            </button>
            <span className="text-[10px] font-bold text-[#5B5F4A]">
              Page {page} of {totalPages}
            </span>
            <button
              onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
              disabled={page === totalPages}
              className="btn-secondary py-1 px-3 text-[10px] font-semibold"
            >
              Next
            </button>
          </div>
        )}
      </div>

      {/* --- ADD TARGET MODAL --- */}
      {isAddOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-500/20 p-4 backdrop-blur-xs">
          <div className="relative w-full max-w-md rounded-xl border border-[#EADFCF] bg-[#FFF9F0] p-6 shadow-2xl animate-in fade-in duration-150">
            <button onClick={closeAddModal} className="absolute top-4 right-4 text-[#5B5F4A]/70 hover:text-[#1E293B]">
              <X className="h-4 w-4" />
            </button>
            <h3 className="text-sm font-bold uppercase tracking-wider text-[#1E293B] mb-1">Add Company</h3>
            <p className="text-[10px] text-[#5B5F4A] mb-6">Setup careers board details for daily scrapes</p>
            
            <form onSubmit={(e) => handleCreate(e, false)} className="space-y-4">
              {formError && (
                <div className="flex items-center gap-2 rounded-xl border border-red-200 bg-red-50 p-3 text-xs text-[#C53030] font-semibold animate-in fade-in">
                  <AlertCircle className="h-4 w-4 shrink-0 text-[#C53030]" />
                  <span>{formError}</span>
                </div>
              )}

              {/* Company Name */}
              <div className="space-y-1">
                <label className="text-[10px] font-bold uppercase tracking-wider text-[#5B5F4A]">Company Name</label>
                <input
                  type="text"
                  required
                  placeholder="e.g. Cloudflare"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  className="w-full rounded-xl border border-[#EADFCF] bg-[#FFFDFC] px-3 py-2 text-xs text-[#1E293B] outline-none focus:border-[#2F6F5E] focus:ring-2 focus:ring-[#2F6F5E]/10 transition"
                />
              </div>

              {/* ATS Platform */}
              <div className="space-y-1">
                <label className="text-[10px] font-bold uppercase tracking-wider text-[#5B5F4A]">ATS Provider Type</label>
                <div className="relative">
                  <select
                    value={ats}
                    onChange={(e) => setAts(e.target.value)}
                    className="w-full appearance-none rounded-xl border border-[#EADFCF] bg-[#FFFDFC] pl-3 pr-8.5 py-2 text-xs text-[#1E293B] outline-none focus:border-[#2F6F5E] transition cursor-pointer font-semibold text-[#5B5F4A]"
                  >
                    <option value="greenhouse">Greenhouse API</option>
                    <option value="lever">Lever API</option>
                    <option value="ashby">Ashby API</option>
                    <option value="workday">Workday API</option>
                    <option value="playwright">Playwright Custom Crawler</option>
                    <option value="all">All (Auto-Detect)</option>
                  </select>
                  <ChevronDown className="absolute right-3.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-[#5B5F4A] pointer-events-none" />
                </div>
              </div>

              {/* ATS Token */}
              {ats !== "playwright" && (
                <div className="space-y-1">
                  <label className="text-[10px] font-bold uppercase tracking-wider text-[#5B5F4A]">
                    ATS Token Slug{ats === "all" && <span className="font-normal text-[#5B5F4A]/60 normal-case tracking-normal"> (optional for Auto-Detect)</span>}
                    {ats === "workday" && <span className="font-normal text-[#5B5F4A]/60 normal-case tracking-normal"> (tenant.data_center.site)</span>}
                  </label>
                  <input
                    type="text"
                    required={ats !== "all"}
                    placeholder={ats === "all" ? "e.g. cloudflare (optional if URL provided)" : ats === "workday" ? "e.g. amgen.wd1.Careers" : "e.g. cloudflare"}
                    value={token}
                    onChange={(e) => setToken(e.target.value)}
                    className="w-full rounded-xl border border-[#EADFCF] bg-[#FFFDFC] px-3 py-2 text-xs text-[#1E293B] outline-none focus:border-[#2F6F5E] focus:ring-2 focus:ring-[#2F6F5E]/10 transition"
                  />
                </div>
              )}

              {/* Careers URL */}
              <div className="space-y-1">
                <label className="text-[10px] font-bold uppercase tracking-wider text-[#5B5F4A]">Careers Page URL</label>
                <input
                  type="url"
                  placeholder="https://..."
                  value={careersUrl}
                  onChange={(e) => setCareersUrl(e.target.value)}
                  className="w-full rounded-xl border border-[#EADFCF] bg-[#FFFDFC] px-3 py-2 text-xs text-[#1E293B] outline-none focus:border-[#2F6F5E] focus:ring-2 focus:ring-[#2F6F5E]/10 transition"
                />
              </div>

              {/* Action buttons */}
              <div className="flex gap-2.5 justify-end pt-4 border-t border-[#EADFCF]">
                <button
                  type="button"
                  onClick={closeAddModal}
                  className="btn-secondary py-1.5 px-3 text-[10px] font-semibold rounded-xl"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={createMutation.isPending}
                  className="btn-secondary py-1.5 px-3 text-[10px] font-semibold rounded-xl"
                >
                  {createMutation.isPending ? "Saving..." : "Save Config"}
                </button>
                <button
                  type="button"
                  onClick={(e) => handleCreate(e, true)}
                  disabled={createMutation.isPending || scrapeMutation.isPending}
                  className="btn-primary py-1.5 px-3 text-[10px] font-semibold bg-[#C67C2E] text-white hover:bg-[#A9621C] rounded-xl"
                >
                  {createMutation.isPending || scrapeMutation.isPending ? "Scraping..." : "Save & Scrape"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* --- EDIT MODAL --- */}
      {isEditOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-500/20 p-4 backdrop-blur-xs">
          <div className="relative w-full max-w-md rounded-xl border border-[#EADFCF] bg-[#FFF9F0] p-6 shadow-2xl animate-in fade-in duration-150">
            <button onClick={closeEditModal} className="absolute top-4 right-4 text-[#5B5F4A]/70 hover:text-[#1E293B]">
              <X className="h-4 w-4" />
            </button>
            <h3 className="text-sm font-bold uppercase tracking-wider text-[#1E293B] mb-1">Edit Target config</h3>
            <p className="text-[10px] text-[#5B5F4A] mb-6">Modify board configuration variables</p>
            
            <form onSubmit={handleUpdate} className="space-y-4">
              {formError && (
                <div className="flex items-center gap-2 rounded-xl border border-red-200 bg-red-50 p-3 text-xs text-[#C53030] font-semibold animate-in fade-in">
                  <AlertCircle className="h-4 w-4 shrink-0 text-[#C53030]" />
                  <span>{formError}</span>
                </div>
              )}

              {/* Company Name */}
              <div className="space-y-1">
                <label className="text-[10px] font-bold uppercase tracking-wider text-[#5B5F4A]">Company Name</label>
                <input
                  type="text"
                  required
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  className="w-full rounded-xl border border-[#EADFCF] bg-[#FFFDFC] px-3 py-2 text-xs text-[#1E293B] outline-none focus:border-[#2F6F5E] focus:ring-2 focus:ring-[#2F6F5E]/10 transition"
                />
              </div>

              {/* ATS Platform */}
              <div className="space-y-1">
                <label className="text-[10px] font-bold uppercase tracking-wider text-[#5B5F4A]">ATS Provider Type</label>
                <div className="relative">
                  <select
                    value={ats}
                    onChange={(e) => setAts(e.target.value)}
                    className="w-full appearance-none rounded-xl border border-[#EADFCF] bg-[#FFFDFC] pl-3 pr-8.5 py-2 text-xs text-[#1E293B] outline-none focus:border-[#2F6F5E] transition cursor-pointer font-semibold text-[#5B5F4A]"
                  >
                    <option value="greenhouse">Greenhouse API</option>
                    <option value="lever">Lever API</option>
                    <option value="ashby">Ashby API</option>
                    <option value="workday">Workday API</option>
                    <option value="playwright">Playwright Custom Scraper</option>
                    <option value="all">All (Auto-Detect)</option>
                  </select>
                  <ChevronDown className="absolute right-3.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-[#5B5F4A] pointer-events-none" />
                </div>
              </div>

              {/* ATS Token */}
              {ats !== "playwright" && (
                <div className="space-y-1">
                  <label className="text-[10px] font-bold uppercase tracking-wider text-[#5B5F4A]">
                    ATS Token Slug{ats === "all" && <span className="font-normal text-[#5B5F4A]/60 normal-case tracking-normal"> (optional for Auto-Detect)</span>}
                    {ats === "workday" && <span className="font-normal text-[#5B5F4A]/60 normal-case tracking-normal"> (tenant.data_center.site)</span>}
                  </label>
                  <input
                    type="text"
                    required={ats !== "all"}
                    placeholder={ats === "all" ? "e.g. cloudflare (optional if URL provided)" : ats === "workday" ? "e.g. amgen.wd1.Careers" : "e.g. cloudflare"}
                    value={token}
                    onChange={(e) => setToken(e.target.value)}
                    className="w-full rounded-xl border border-[#EADFCF] bg-[#FFFDFC] px-3 py-2 text-xs text-[#1E293B] outline-none focus:border-[#2F6F5E] focus:ring-2 focus:ring-[#2F6F5E]/10 transition"
                  />
                </div>
              )}

              {/* Careers URL */}
              <div className="space-y-1">
                <label className="text-[10px] font-bold uppercase tracking-wider text-[#5B5F4A]">Careers Page URL</label>
                <input
                  type="url"
                  value={careersUrl}
                  onChange={(e) => setCareersUrl(e.target.value)}
                  className="w-full rounded-xl border border-[#EADFCF] bg-[#FFFDFC] px-3 py-2 text-xs text-[#1E293B] outline-none focus:border-[#2F6F5E] focus:ring-2 focus:ring-[#2F6F5E]/10 transition"
                />
              </div>

              {/* Action Buttons */}
              <div className="flex gap-2.5 justify-end pt-4 border-t border-[#EADFCF]">
                <button
                  type="button"
                  onClick={closeEditModal}
                  className="btn-secondary py-1.5 px-3 text-[10px] font-semibold rounded-xl"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={updateMutation.isPending}
                  className="btn-primary py-1.5 px-4 text-[10px] font-semibold bg-[#C67C2E] text-white hover:bg-[#A9621C] rounded-xl"
                >
                  {updateMutation.isPending ? "Saving..." : "Save Changes"}
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
            <h3 className="text-xs font-bold uppercase tracking-wider text-[#1E293B] mb-2">Delete configuration</h3>
            <p className="text-xs text-[#5B5F4A] mb-5 leading-normal">
              Confirm deleting <span className="text-[#1E293B] font-semibold">{currentCompany?.name}</span>? Scrapers will bypass this target in daily executions.
            </p>
            <div className="flex gap-2 justify-end">
              <button
                onClick={() => setIsDeleteOpen(false)}
                className="btn-secondary py-1.5 px-3 text-[10px] font-semibold rounded-xl"
              >
                Cancel
              </button>
              <button
                onClick={() => deleteMutation.mutate(currentCompany.id)}
                disabled={deleteMutation.isPending}
                className="rounded-xl bg-[#C53030] px-3 py-1.5 text-[10px] font-bold text-white hover:bg-[#A92222] active:scale-95 transition cursor-pointer"
              >
                {deleteMutation.isPending ? "Deleting..." : "Delete Target"}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* --- SCRAPER PROGRESS LOADER --- */}
      {scrapeLoading && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-500/20 p-4 backdrop-blur-xs">
          <div className="flex flex-col items-center gap-3 text-center bg-[#FFF9F0] border border-[#EADFCF] p-6 rounded-xl shadow-lg animate-in fade-in duration-150">
            <Loader2 className="h-8 w-8 animate-spin text-[#2F6F5E]" />
            <div className="space-y-1">
              <h3 className="text-xs font-bold uppercase tracking-widest text-[#1E293B]">Aggregating Target Careers</h3>
              <p className="text-[10px] text-[#5B5F4A] max-w-xs leading-normal">
                Connecting to ATS services, parsing experience rules, and executing AI validations...
              </p>
            </div>
          </div>
        </div>
      )}

      {/* --- SCRAPER RESULTS OVERLAY MODAL --- */}
      {isScrapeResultOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-500/20 p-4 backdrop-blur-xs">
          <div className="relative w-full max-w-xl rounded-xl border border-[#EADFCF] bg-[#FFF9F0] p-6 shadow-2xl animate-in fade-in duration-150 max-h-[75vh] flex flex-col">
            <button onClick={() => { setIsScrapeResultOpen(false); setIsAddOpen(false); }} className="absolute top-4 right-4 text-[#5B5F4A]/70 hover:text-[#1E293B]">
              <X className="h-4 w-4" />
            </button>
            
            <div className="flex items-center gap-2 mb-1.5">
              <Check className="h-4.5 w-4.5 text-[#2E7D32]" />
              <h3 className="text-sm font-bold uppercase tracking-wider text-[#1E293B]">Aggregation Summary</h3>
            </div>
            <p className="text-[10px] text-[#5B5F4A] mb-5 border-b border-[#EADFCF] pb-2.5 leading-normal">
              {scrapeResult?.log}
            </p>
            
            {/* List of scraped jobs */}
            <div className="flex-1 overflow-y-auto space-y-2 pr-1">
              <h4 className="text-[10px] font-bold uppercase tracking-widest text-[#5B5F4A]">New Leads Found ({scrapeResult?.new_jobs_added})</h4>
              
              {scrapeResult?.jobs?.length > 0 ? (
                scrapeResult.jobs.map((job: any, index: number) => (
                  <div key={index} className="flex justify-between items-center bg-[#FFF9F0]/40 border border-[#EADFCF] p-2.5 rounded-xl gap-4 hover:border-[#D1C4B2]">
                    <div className="min-w-0">
                      <p className="text-xs font-semibold text-[#1E293B] truncate leading-snug">{job.title}</p>
                      <p className="text-[10px] text-[#5B5F4A] mt-0.5">{job.location || "Location not configured"}</p>
                    </div>
                    <a
                      href={job.link}
                      target="_blank"
                      className="inline-flex items-center gap-1 text-[10px] font-bold text-[#C67C2E] hover:underline transition shrink-0"
                    >
                      <span>Apply</span>
                      <ExternalLink className="h-3 w-3" />
                    </a>
                  </div>
                ))
              ) : (
                <div className="flex flex-col items-center justify-center py-8 text-[#5B5F4A]">
                  <Building2 className="h-8 w-8 text-[#EADFCF] mb-2" />
                  <p className="text-xs leading-normal">No fresh matching job postings identified during this sweep.</p>
                </div>
              )}
            </div>

            <div className="mt-5 flex justify-end border-t border-[#EADFCF] pt-4">
              <button
                onClick={() => { setIsScrapeResultOpen(false); setIsAddOpen(false); }}
                className="btn-primary py-1.5 px-4 text-[10px] font-semibold bg-[#C67C2E] text-white hover:bg-[#A9621C] rounded-xl"
              >
                Close Summary
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
