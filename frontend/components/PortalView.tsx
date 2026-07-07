import React, { useState, useEffect } from 'react';
import {
  searchVerifiedArticles,
  getArticleById,
  SearchResultItem,
  getValidAccessToken,
  exportSearchCsv
} from '../services/apiService';
import { VerificationResult } from '../types';

interface PortalViewProps {
  isDarkMode: boolean;
}

const PortalView: React.FC<PortalViewProps> = ({ isDarkMode }) => {
  // Search parameters
  const [keyword, setKeyword] = useState('');
  const [status, setStatus] = useState('all');
  const [language, setLanguage] = useState('all');
  const [platform, setPlatform] = useState('all');
  const [dateFrom, setDateFrom] = useState('');
  const [dateTo, setDateTo] = useState('');
  
  // Results & Pagination
  const [results, setResults] = useState<SearchResultItem[]>([]);
  const [totalCount, setTotalCount] = useState(0);
  const [currentPage, setCurrentPage] = useState(1);
  const [perPage, setPerPage] = useState(20);
  
  // States
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState('');
  const [selectedReport, setSelectedReport] = useState<VerificationResult | null>(null);
  const [isLoadingDetails, setIsLoadingDetails] = useState(false);
  const [csvExporting, setCsvExporting] = useState(false);

  const handleExportCsv = async () => {
    setCsvExporting(true);
    try {
      const token = await getValidAccessToken();
      if (!token) {
        alert('Please log in to export search results to CSV.');
        return;
      }

      const blob = await exportSearchCsv(token, {
        q: keyword || undefined,
        status: status !== 'all' ? status : undefined,
        language: language !== 'all' ? language : undefined,
        platform: platform !== 'all' ? platform : undefined,
        date_from: dateFrom || undefined,
        date_to: dateTo || undefined,
        limit: 1000
      });

      const url = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      const queryPart = keyword ? `_${keyword.replace(/\s+/g, '_')}` : '';
      link.setAttribute('download', `verified_reports${queryPart}_export.csv`);
      document.body.appendChild(link);
      link.click();
      link.parentNode?.removeChild(link);
      window.URL.revokeObjectURL(url);
    } catch (err: any) {
      console.error(err);
      alert(err.message || 'Failed to export CSV.');
    } finally {
      setCsvExporting(false);
    }
  };

  // Run search on load and when filters change
  useEffect(() => {
    fetchResults(1);
  }, [status, language, platform, dateFrom, dateTo]);

  const fetchResults = async (
    page: number,
    overrides?: {
      q?: string;
      status?: string;
      language?: string;
      platform?: string;
      date_from?: string;
      date_to?: string;
      limit?: number;
    }
  ) => {
    setIsLoading(true);
    setError('');
    try {
      const activeLimit = overrides && 'limit' in overrides ? overrides.limit! : perPage;
      const offset = (page - 1) * activeLimit;
      const searchKeyword = overrides && 'q' in overrides ? overrides.q : keyword;
      const statusVal = overrides && 'status' in overrides ? overrides.status : status;
      const languageVal = overrides && 'language' in overrides ? overrides.language : language;
      const platformVal = overrides && 'platform' in overrides ? overrides.platform : platform;
      const dateFromVal = overrides && 'date_from' in overrides ? overrides.date_from : dateFrom;
      const dateToVal = overrides && 'date_to' in overrides ? overrides.date_to : dateTo;

      const data = await searchVerifiedArticles({
        q: searchKeyword || undefined,
        status: statusVal !== 'all' ? statusVal : undefined,
        language: languageVal !== 'all' ? languageVal : undefined,
        platform: platformVal !== 'all' ? platformVal : undefined,
        date_from: dateFromVal || undefined,
        date_to: dateToVal || undefined,
        limit: activeLimit,
        offset: offset
      });
      setResults(data.results);
      setTotalCount(data.total_count);
      setCurrentPage(data.page);
    } catch (err: any) {
      console.error(err);
      setError(err.message || 'Failed to search verified articles.');
    } finally {
      setIsLoading(false);
    }
  };

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    fetchResults(1);
  };

  const handlePageChange = (newPage: number) => {
    fetchResults(newPage);
  };

  const handleCardClick = async (articleId: string) => {
    setIsLoadingDetails(true);
    try {
      const details = await getArticleById(articleId);
      setSelectedReport(details);
    } catch (err: any) {
      console.error("Failed to fetch verification details:", err);
      alert(err.message || 'Failed to fetch verification details.');
    } finally {
      setIsLoadingDetails(false);
    }
  };

  const getVerdictBadgeClass = (verdict: string) => {
    const v = verdict.toUpperCase();
    if (v.includes('REAL')) return 'bg-emerald-500/10 text-emerald-500 border border-emerald-500/20';
    if (v.includes('FAKE')) return 'bg-rose-500/10 text-rose-500 border border-rose-500/20';
    return 'bg-amber-500/10 text-amber-500 border border-amber-500/20';
  };

  const getPlatformIcon = (plat: string | undefined | null) => {
    if (!plat) return '📰';
    const p = plat.toLowerCase();
    if (p === 'twitter' || p === 'x') return '🐦';
    if (p === 'reddit') return '👽';
    if (p === 'telegram') return '✈️';
    if (p === 'website' || p === 'web' || p.includes('.')) return '🌐';
    return '📰';
  };

  const getPlatformLabel = (plat: string | undefined | null) => {
    if (!plat) return 'Source';
    const p = plat.toLowerCase();
    if (p === 'twitter' || p === 'x') return 'Twitter';
    if (p === 'reddit') return 'Reddit';
    if (p === 'telegram') return 'Telegram';
    if (p === 'website' || p === 'web') return 'Website';
    // Handles domain names like 'chinapress.com.my'
    if (p.includes('.')) return 'Website';
    return plat;
  };

  const totalPages = Math.ceil(totalCount / perPage);

  // Extracts a clean title from raw article text.
  // If the text looks like a URL, returns 'External Article (domain)'.
  // Otherwise returns the first meaningful sentence/line (max 80 chars).
  const extractTitle = (text: string | undefined): string => {
    if (!text) return 'Untitled Article';
    const trimmed = text.trim();
    // URL detection
    if (/^https?:\/\//i.test(trimmed)) {
      try {
        const url = new URL(trimmed);
        return `External Article (${url.hostname.replace('www.', '')})`;
      } catch {
        return 'External Article';
      }
    }
    // Take first sentence or first line
    const firstPart = trimmed.split(/[\n.]/)[0].trim();
    if (firstPart.length > 80) return firstPart.substring(0, 77) + '...';
    return firstPart || trimmed.substring(0, 80);
  };

  // Highlights the search keyword within a text string.
  const highlightKeyword = (text: string, kw: string): React.ReactNode => {
    if (!kw || !kw.trim()) return text;
    const safeKw = kw.trim().replace(/[.*+?^${}()|[\]\\]/g, '\\  const totalPages = Math.ceil(totalCount / perPage);');
    const regex = new RegExp(`(${safeKw})`, 'gi');
    const parts = text.split(regex);
    return parts.map((part, i) =>
      regex.test(part) ? (
        <mark key={i} className="bg-yellow-300/60 text-inherit rounded px-0.5">{part}</mark>
      ) : (
        part
      )
    );
  };

  const cardClass = `p-6 rounded-2xl border transition-all duration-300 hover:scale-[1.01] hover:shadow-lg cursor-pointer flex flex-col h-full ${
    isDarkMode ? 'bg-[#1E293B] border-[#334155] hover:border-emerald-500/30' : 'bg-white border-[#E2E8F0] shadow-sm hover:border-emerald-500/30'
  }`;

  const selectClass = `px-4 py-2.5 rounded-xl border focus:ring-2 focus:ring-emerald-500 outline-none transition-all text-xs font-semibold ${
    isDarkMode ? 'bg-[#0F172A] border-[#334155] text-white' : 'bg-[#F8FAFC] border-[#E2E8F0] text-slate-800'
  }`;

  const inputClass = `px-4 py-2 rounded-xl border focus:ring-2 focus:ring-emerald-500 outline-none transition-all text-xs ${
    isDarkMode ? 'bg-[#0F172A] border-[#334155] text-white' : 'bg-[#F8FAFC] border-[#E2E8F0] text-slate-800'
  }`;

  return (
    <div className="space-y-8 animate-fade-in">
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-end gap-4">
        <div>
          <h2 className="text-3xl font-black tracking-tight">Public Truth Portal</h2>
          <p className={isDarkMode ? 'text-[#94A3B8]' : 'text-slate-500'}>
            Explore and search all news accuracy verifications globally verified by the engine.
          </p>
        </div>
      </div>

      {/* Search Bar & Filters */}
      <form onSubmit={handleSearchSubmit} className={`p-6 rounded-2xl border space-y-4 ${
        isDarkMode ? 'bg-[#1E293B] border-[#334155]' : 'bg-white border-[#E2E8F0] shadow-sm'
      }`}>
        <div className="flex flex-col md:flex-row gap-4">
          <div className="relative flex-1">
            <input
              type="text"
              value={keyword}
              onChange={(e) => setKeyword(e.target.value)}
              placeholder="Search by keywords (e.g. Bitcoin, SEC, airdrop)..."
              className={`w-full pl-10 pr-4 py-3 rounded-xl border focus:ring-2 focus:ring-emerald-500 outline-none transition-all text-sm ${
                isDarkMode ? 'bg-[#0F172A] border-[#334155] text-white' : 'bg-[#F8FAFC] border-[#E2E8F0] text-slate-800'
              }`}
            />
            <span className="absolute left-3.5 top-3.5 text-slate-400">
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
              </svg>
            </span>
          </div>
          <button
            type="submit"
            className="bg-emerald-500 hover:bg-emerald-600 text-white px-8 py-3 rounded-xl font-bold transition-all shadow-lg shadow-emerald-500/20 active:scale-95"
          >
            Search
          </button>
        </div>

        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-2.5">
          {/* Status filter */}
          <select value={status} onChange={(e) => setStatus(e.target.value)} className={selectClass}>
            <option value="all">All Verdicts</option>
            <option value="real">Real</option>
            <option value="fake">Fake</option>
            <option value="uncertain">Uncertain</option>
          </select>

          {/* Language filter */}
          <select value={language} onChange={(e) => setLanguage(e.target.value)} className={selectClass}>
            <option value="all">All Languages</option>
            <option value="en">English</option>
            <option value="zh">Chinese</option>
            <option value="ms">Malay</option>
          </select>

          {/* Platform filter */}
          <select value={platform} onChange={(e) => setPlatform(e.target.value)} className={selectClass}>
            <option value="all">All Platforms</option>
            <option value="twitter">Twitter</option>
            <option value="reddit">Reddit</option>
            <option value="telegram">Telegram</option>
            <option value="website">Website / News</option>
          </select>

          {/* Date from */}
          <input
            type="date"
            value={dateFrom}
            onChange={(e) => setDateFrom(e.target.value)}
            className={inputClass}
          />

          {/* Date to */}
          <input
            type="date"
            value={dateTo}
            onChange={(e) => setDateTo(e.target.value)}
            className={inputClass}
          />

          {/* Clear Filters */}
          <button
            type="button"
            onClick={() => {
              setKeyword('');
              setStatus('all');
              setLanguage('all');
              setPlatform('all');
              setDateFrom('');
              setDateTo('');
              fetchResults(1, {
                q: '',
                status: 'all',
                language: 'all',
                platform: 'all',
                date_from: '',
                date_to: ''
              });
            }}
            className={`px-4 py-2.5 rounded-xl border text-xs font-bold transition-all col-span-2 md:col-span-1 ${
              isDarkMode ? 'border-[#334155] text-slate-400 hover:bg-[#0F172A]' : 'border-[#E2E8F0] text-slate-600 hover:bg-slate-50'
            }`}
          >
            ✕ Clear Filters
          </button>
        </div>
      </form>

      {/* Toolbar: per-page selector (right) + Export CSV (right) */}
      <div className="flex flex-wrap items-center justify-end gap-3">
        <div className="flex items-center gap-2">
          <span className={`text-xs font-bold uppercase opacity-50`}>Show</span>
          <select
            value={perPage}
            onChange={(e) => {
              const newLimit = Number(e.target.value);
              setPerPage(newLimit);
              setCurrentPage(1);
              fetchResults(1, { limit: newLimit });
            }}
            className={selectClass}
          >
            <option value={10}>10 / page</option>
            <option value={20}>20 / page</option>
            <option value={30}>30 / page</option>
            <option value={50}>50 / page</option>
          </select>
        </div>

        <button
          type="button"
          disabled={csvExporting}
          onClick={handleExportCsv}
          className={`px-4 py-2.5 rounded-xl border text-xs font-bold transition-all flex items-center justify-center gap-1.5 active:scale-95 ${
            csvExporting
              ? 'opacity-50 cursor-not-allowed'
              : isDarkMode
              ? 'border-emerald-500/30 text-emerald-400 hover:bg-emerald-500/10'
              : 'border-emerald-500/30 text-emerald-600 hover:bg-emerald-50'
          }`}
        >
          {csvExporting ? (
            <>
              <svg className="animate-spin h-3.5 w-3.5 text-current" fill="none" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
              </svg>
              <span>Exporting...</span>
            </>
          ) : (
            <><span>📥 Export CSV</span></>
          )}
        </button>
      </div>

      {/* Grid of Results */}
      {isLoading ? (
        <div className="flex items-center justify-center py-20">
          <div className="w-12 h-12 border-4 border-emerald-500 border-t-transparent rounded-full animate-spin"></div>
        </div>
      ) : error ? (
        <div className="text-center py-12 text-rose-500 font-semibold">{error}</div>
      ) : results.length === 0 ? (
        <div className="text-center py-20 border-2 border-dashed border-slate-300 dark:border-slate-800 rounded-3xl opacity-50">
          No verified reports matching the selected filters.
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-5">
          {results.map((item) => (
            <div key={item.article_id} className={cardClass} onClick={() => handleCardClick(item.article_id)}>
              <div className="flex justify-between items-start mb-4">
                <span className={`px-2.5 py-1 text-[10px] font-black rounded uppercase tracking-wider ${getVerdictBadgeClass(item.classification.verdict)}`}>
                  {item.classification.verdict}
                </span>
                <div className="flex items-center gap-2 text-[10px] opacity-50 font-semibold">
                  <span>{getPlatformIcon(item.platform)} {getPlatformLabel(item.platform)}</span>
                  <span>•</span>
                  <span>{(item.language || 'en').toUpperCase()}</span>
                </div>
              </div>
              <p className="font-bold text-sm mb-2 leading-snug line-clamp-2">
                {highlightKeyword(item.title || extractTitle(item.text), keyword)}
              </p>
              {keyword && (
                <p className={`text-[11px] mb-4 leading-relaxed line-clamp-2 ${isDarkMode ? 'text-slate-400' : 'text-slate-500'}`}>
                  {highlightKeyword(item.text, keyword)}
                </p>
              )}
              <div className="flex justify-between items-center text-[10px] opacity-40 font-bold border-t pt-4 mt-auto border-slate-200/20">
                <span>ID: {(item.article_id || '').substring(0, 8)}...</span>
                <span>{item.created_at ? new Date(item.created_at).toLocaleDateString() : 'N/A'}</span>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Pagination */}
      {!isLoading && totalPages > 1 && (
        <div className="flex flex-col items-center gap-3 mt-8">
          <p className={`text-xs font-semibold opacity-50`}>
            Showing {Math.min((currentPage - 1) * perPage + 1, totalCount)}–{Math.min(currentPage * perPage, totalCount)} of {totalCount} results
          </p>
          <div className="flex justify-center items-center gap-2">
            <button
              disabled={currentPage === 1}
              onClick={() => handlePageChange(1)}
              className={`px-3 py-2 rounded-xl text-xs font-bold border transition-all ${
                currentPage === 1
                  ? 'opacity-40 cursor-not-allowed border-transparent'
                  : isDarkMode ? 'border-[#334155] hover:bg-[#1E293B]' : 'border-[#E2E8F0] hover:bg-slate-50'
              }`}
            >
              «
            </button>
            <button
              disabled={currentPage === 1}
              onClick={() => handlePageChange(currentPage - 1)}
              className={`px-4 py-2 rounded-xl text-xs font-bold border transition-all ${
                currentPage === 1
                  ? 'opacity-40 cursor-not-allowed border-transparent'
                  : isDarkMode ? 'border-[#334155] hover:bg-[#1E293B]' : 'border-[#E2E8F0] hover:bg-slate-50'
              }`}
            >
              ‹ Prev
            </button>
            {(() => {
              const pages: (number | '...')[] = [];
              if (totalPages <= 7) {
                for (let i = 1; i <= totalPages; i++) pages.push(i);
              } else {
                pages.push(1);
                if (currentPage > 3) pages.push('...');
                for (let i = Math.max(2, currentPage - 1); i <= Math.min(totalPages - 1, currentPage + 1); i++) {
                  pages.push(i);
                }
                if (currentPage < totalPages - 2) pages.push('...');
                pages.push(totalPages);
              }
              return pages.map((p, idx) =>
                p === '...' ? (
                  <span key={`ellipsis-${idx}`} className="px-1 text-xs opacity-40">…</span>
                ) : (
                  <button
                    key={p}
                    onClick={() => handlePageChange(p as number)}
                    className={`w-8 h-8 rounded-xl text-xs font-bold border transition-all ${
                      currentPage === p
                        ? 'bg-emerald-500 border-emerald-500 text-white'
                        : isDarkMode ? 'border-[#334155] hover:bg-[#1E293B]' : 'border-[#E2E8F0] hover:bg-slate-50'
                    }`}
                  >
                    {p}
                  </button>
                )
              );
            })()}
            <button
              disabled={currentPage === totalPages}
              onClick={() => handlePageChange(currentPage + 1)}
              className={`px-4 py-2 rounded-xl text-xs font-bold border transition-all ${
                currentPage === totalPages
                  ? 'opacity-40 cursor-not-allowed border-transparent'
                  : isDarkMode ? 'border-[#334155] hover:bg-[#1E293B]' : 'border-[#E2E8F0] hover:bg-slate-50'
              }`}
            >
              Next ›
            </button>
            <button
              disabled={currentPage === totalPages}
              onClick={() => handlePageChange(totalPages)}
              className={`px-3 py-2 rounded-xl text-xs font-bold border transition-all ${
                currentPage === totalPages
                  ? 'opacity-40 cursor-not-allowed border-transparent'
                  : isDarkMode ? 'border-[#334155] hover:bg-[#1E293B]' : 'border-[#E2E8F0] hover:bg-slate-50'
              }`}
            >
              »
            </button>
          </div>
        </div>
      )}

      {/* Details Modal (Centered overlay) */}
      {selectedReport && (
        <div className="fixed inset-0 z-[100] flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm animate-fade-in">
          <div className={`w-full max-w-4xl max-h-[90vh] overflow-y-auto p-8 rounded-3xl border shadow-2xl relative ${
            isDarkMode ? 'bg-[#0F172A] border-[#334155] text-white' : 'bg-[#F8FAFC] border-[#E2E8F0] text-slate-800'
          }`}>
            {/* Close Button */}
            <button 
              onClick={() => setSelectedReport(null)}
              className="absolute top-6 right-6 p-2 rounded-full border border-slate-200/20 hover:scale-105 active:scale-95 transition-all text-slate-400 hover:text-white"
            >
              <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>

            <div className="space-y-4 mt-6">
              <div>
                <span className="text-[9px] font-black tracking-widest text-emerald-500 uppercase">Verification Report Details</span>
                <h3 className="text-2xl font-black mt-1 leading-snug">{selectedReport.title || extractTitle(selectedReport.text)}</h3>
                {/* Original source link if it's a URL */}
                {selectedReport.text && /^https?:\/\//i.test(selectedReport.text.trim()) && (
                  <a
                    href={selectedReport.text.trim()}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center gap-1.5 mt-2 text-xs font-semibold text-emerald-500 hover:text-emerald-400 hover:underline"
                  >
                    <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" /></svg>
                    View Original Article
                  </a>
                )}
              </div>

              {/* Full article text (collapsible context) */}
              {selectedReport.text && !/^https?:\/\//i.test(selectedReport.text.trim()) && (
                <div className={`p-4 rounded-xl border text-sm leading-relaxed ${isDarkMode ? 'bg-[#1E293B] border-[#334155] text-slate-300' : 'bg-slate-50 border-slate-200 text-slate-600'}`}>
                  {selectedReport.text}
                </div>
              )}

              {/* Grid Details */}
              <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                
                {/* Verdict Info */}
                {(() => {
                  const label = selectedReport.finalAssessment?.label || selectedReport.status || 'UNCERTAIN';
                  const score = selectedReport.finalAssessment ? selectedReport.finalAssessment.score : (selectedReport.confidence ?? 0.5);
                  const verdictUpper = label.toUpperCase().replace('_', ' ');
                  const verdictColor = verdictUpper.includes('REAL') ? 'text-emerald-500' : verdictUpper.includes('FAKE') ? 'text-rose-500' : 'text-amber-500';
                  const verdictBg = verdictUpper.includes('REAL') ? 'bg-emerald-500/10 border-emerald-500/20' : verdictUpper.includes('FAKE') ? 'bg-rose-500/10 border-rose-500/20' : 'bg-amber-500/10 border-amber-500/20';
                  const isFakeVerdict = verdictUpper.includes('FAKE');
                  const displayConfidence = selectedReport.finalAssessment
                    ? (isFakeVerdict ? score : (1 - score))
                    : (selectedReport.confidence ?? 0.5);

                  return (
                    <div className={`md:col-span-3 p-6 rounded-2xl border flex flex-col md:flex-row items-center justify-between gap-6 ${verdictBg}`}>
                      <div>
                        <h4 className={`text-3xl font-black uppercase tracking-tight ${verdictColor}`}>
                           VERDICT: {verdictUpper}
                        </h4>
                        <p className="text-xs opacity-80 mt-1 max-w-xl">
                          {selectedReport.finalAssessment?.reasoning || 
                           (typeof selectedReport.explanation === 'string' 
                             ? selectedReport.explanation 
                             : selectedReport.explanation?.summary) || 
                           selectedReport.classification?.explanation || 
                           ''}
                        </p>
                      </div>
                      <div className="flex gap-6 shrink-0 border-l border-slate-200/20 pl-6">
                        <div className="text-center">
                          <span className="block text-[9px] font-bold uppercase opacity-50">Confidence</span>
                          <span className="text-2xl font-black">{(displayConfidence * 100).toFixed(0)}%</span>
                        </div>
                        {selectedReport.processingTimeMs && (
                          <div className="text-center">
                            <span className="block text-[9px] font-bold uppercase opacity-50">Latency</span>
                            <span className="text-xl font-black">{selectedReport.processingTimeMs} ms</span>
                          </div>
                        )}
                      </div>
                    </div>
                  );
                })()}

                {/* AI Summary */}
                {(() => {
                  const aiSummary = selectedReport.verification?.summary || (selectedReport.verification as any)?.explanation || '';
                  if (!aiSummary) return null;
                  return (
                    <div className={`md:col-span-3 p-6 rounded-2xl border ${isDarkMode ? 'bg-[#1E293B] border-[#334155]' : 'bg-white border-[#E2E8F0] shadow-sm'}`}>
                      <h4 className="text-lg font-bold mb-3 flex items-center gap-2">
                        <svg className="w-5 h-5 text-emerald-600" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" /></svg>
                        AI Analysis Summary
                      </h4>
                      <p className={`text-sm leading-relaxed ${isDarkMode ? 'text-slate-300' : 'text-slate-600'}`}>
                        {aiSummary}
                      </p>
                    </div>
                  );
                })()}

                {/* Source Verification */}
                <div className={`p-6 rounded-2xl border min-w-0 ${isDarkMode ? 'bg-[#1E293B] border-[#334155]' : 'bg-white border-[#E2E8F0] shadow-sm'}`}>
                  <h4 className="text-lg font-bold mb-1 flex items-center gap-2">
                    <svg className="w-5 h-5 text-emerald-600" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04M12 2.944a11.955 11.955 0 01-4.532 10.948m14.75 0a11.955 11.955 0 01-4.532 10.948" /></svg>
                    Source Verification
                  </h4>
                  <p className={`text-[10px] mb-4 ${isDarkMode ? 'text-slate-500' : 'text-slate-400'}`}>Cross-referenced against authoritative sources. Click any validated link to view the source article.</p>

                  {(() => {
                    const rawSources = (selectedReport.verification?.sources || selectedReport.sources || []);
                    // Filter out unconfirmed legacy hardcoded sources
                    const sources = rawSources.filter(s => {
                      if (!s || !s.name) return false;
                      const nameLower = s.name.toLowerCase();
                      const isLegacyHardcoded = ["reuters", "bloomberg", "coindesk", "sec"].includes(nameLower);
                      return !(isLegacyHardcoded && !s.confirmed);
                    });

                    const matchingArticles = selectedReport.verification?.matchingArticles || (selectedReport.verification as any)?.matching_articles || [];

                    // Map source name → matching article (case-insensitive)
                    const articleBySource: Record<string, typeof matchingArticles[0]> = {};
                    if (Array.isArray(matchingArticles)) {
                      matchingArticles.forEach(a => {
                        if (a && a.source) {
                          articleBySource[a.source.toLowerCase()] = a;
                        }
                      });
                    }

                    if (sources.length === 0) {
                      return <p className="text-xs opacity-50 italic mt-4">No external sources verified for this claim.</p>;
                    }

                    return (
                      <div className="space-y-2.5">
                        {sources.map((source, idx) => {
                          if (!source || !source.name) return null;
                          const match = articleBySource[source.name.toLowerCase()];
                          return (
                            <div key={idx} className={`rounded-xl border transition-all ${
                              source.confirmed
                                ? isDarkMode ? 'bg-emerald-500/5 border-emerald-500/20' : 'bg-emerald-50/60 border-emerald-200'
                                : isDarkMode ? 'bg-[#0F172A] border-[#1E293B]' : 'bg-slate-50 border-slate-200'
                            }`}>
                              <div className="flex items-center justify-between gap-2 px-3 py-2.5">
                                <div className="flex items-center gap-2 min-w-0">
                                  {/* Favicon */}
                                  <div className={`w-6 h-6 rounded-md flex items-center justify-center shrink-0 ${
                                    source.confirmed ? 'bg-emerald-500' : isDarkMode ? 'bg-slate-700' : 'bg-slate-200'
                                  }`}>
                                    {source.confirmed ? (
                                      <svg className="w-3.5 h-3.5 text-white" fill="currentColor" viewBox="0 0 20 20"><path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" /></svg>
                                    ) : (
                                      <svg className="w-3 h-3 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12" /></svg>
                                    )}
                                  </div>
                                  <span className={`font-bold text-xs truncate ${source.confirmed ? 'text-emerald-600' : isDarkMode ? 'text-slate-400' : 'text-slate-500'}`}>
                                    {source.name}
                                  </span>
                                </div>
                                {source.confirmed ? (
                                  <span className="text-emerald-500 text-[9px] font-black bg-emerald-500/10 px-2 py-0.5 rounded-full border border-emerald-500/30 shrink-0 uppercase tracking-wide">✓ Validated</span>
                                ) : (
                                  <span className="text-slate-400 text-[9px] font-black bg-slate-500/10 px-2 py-0.5 rounded-full border border-slate-400/20 shrink-0 uppercase tracking-wide">No Mention</span>
                                )}
                              </div>

                              {/* Inline proof link when a matching article exists */}
                              {match && (
                                <div className={`px-3 pb-2.5 border-t ${
                                  isDarkMode ? 'border-emerald-500/10' : 'border-emerald-100'
                                }`}>
                                  <a
                                    href={match.link}
                                    target="_blank"
                                    rel="noopener noreferrer"
                                    className="flex items-start gap-2 mt-2 group"
                                  >
                                    <svg className="w-3.5 h-3.5 text-emerald-500 shrink-0 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" /></svg>
                                    <span className="text-[10px] font-semibold text-emerald-500 group-hover:text-emerald-400 group-hover:underline leading-snug line-clamp-2">
                                      {match.title}
                                    </span>
                                  </a>
                                  {match.snippet && (
                                    <p className={`text-[9px] mt-1.5 leading-relaxed line-clamp-2 pl-5 ${
                                      isDarkMode ? 'text-slate-500' : 'text-slate-400'
                                    }`}>
                                      {match.snippet}
                                    </p>
                                  )}
                                </div>
                              )}

                              {/* Show source URL directly if available on the source object */}
                              {!match && source.url && (
                                <div className={`px-3 pb-2.5 border-t ${
                                  isDarkMode ? 'border-emerald-500/10' : 'border-emerald-100'
                                }`}>
                                  <a
                                    href={source.url}
                                    target="_blank"
                                    rel="noopener noreferrer"
                                    className="flex items-center gap-1.5 mt-2 text-[10px] font-semibold text-emerald-500 hover:text-emerald-400 hover:underline"
                                  >
                                    <svg className="w-3.5 h-3.5 text-emerald-500 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" /></svg>
                                    View source
                                  </a>
                                </div>
                              )}
                            </div>
                          );
                        })}
                      </div>
                    );
                  })()}
                </div>

                {/* Feature Attribution */}
                <div className={`p-6 rounded-2xl border min-w-0 ${isDarkMode ? 'bg-[#1E293B] border-[#334155]' : 'bg-white border-[#E2E8F0] shadow-sm'}`}>
                  <h4 className="text-lg font-bold mb-4 flex items-center gap-2">
                    <svg className="w-5 h-5 text-emerald-600" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" /></svg>
                    Feature Attribution
                  </h4>
                  <p className="text-xs mb-6 opacity-60">SHAP values indicating word contribution towards the verdict:</p>
                  <div className="space-y-4">
                     {((selectedReport.explanation && (selectedReport.explanation.shapData || (selectedReport.explanation as any).shap_data)) || selectedReport.shapData || (selectedReport as any).shap_data || []).slice().sort((a,b) => Math.abs(b.weight) - Math.abs(a.weight)).map((item, idx) => (
                      <div key={idx} className="space-y-1.5">
                        <div className="flex justify-between text-[11px] font-bold">
                          <span className="mono bg-slate-100 dark:bg-slate-800 px-1.5 py-0.5 rounded text-emerald-600">"{item.word}"</span>
                          <span className={item.weight > 0 ? 'text-rose-500' : 'text-emerald-500'}>
                            {item.weight > 0 ? '+' : ''}{item.weight.toFixed(3)}
                          </span>
                        </div>
                        <div className={`w-full h-1.5 rounded-full ${isDarkMode ? 'bg-[#0F172A]' : 'bg-slate-100'} overflow-hidden`}>
                          <div 
                            className={`h-full rounded-full transition-all duration-1000 ${item.weight > 0 ? 'bg-rose-500' : 'bg-emerald-500'}`}
                            style={{ width: `${Math.min(Math.abs(item.weight) * 200, 100)}%` }}
                          />
                        </div>
                      </div>
                    ))}
                  </div>
                  <div className="mt-8 grid grid-cols-2 gap-2">
                    <div className={`p-2 rounded-lg border text-center ${
                      (() => {
                        const signal = (selectedReport.explanation as any)?.factualSignal || 'Medium';
                        if (signal === 'High') return 'bg-emerald-500/10 border-emerald-500/20';
                        if (signal === 'Low') return 'bg-rose-500/10 border-rose-500/20';
                        return 'bg-amber-500/10 border-amber-500/20';
                      })()
                    }`}>
                      <span className="block text-[9px] font-bold uppercase text-emerald-600">Factual Signal</span>
                      <span className={`text-xs font-bold ${
                        (() => {
                          const signal = (selectedReport.explanation as any)?.factualSignal || 'Medium';
                          if (signal === 'High') return 'text-emerald-500';
                          if (signal === 'Low') return 'text-rose-500';
                          return 'text-amber-500';
                        })()
                      }`}>{(selectedReport.explanation as any)?.factualSignal || 'Medium'}</span>
                    </div>
                    <div className={`p-2 rounded-lg border text-center ${
                      (() => {
                        const signal = (selectedReport.explanation as any)?.biasSignal || 'Low';
                        if (signal === 'Critical' || signal === 'High') return 'bg-rose-500/10 border-rose-500/20';
                        if (signal === 'Medium') return 'bg-amber-500/10 border-amber-500/20';
                        return 'bg-emerald-500/10 border-emerald-500/20';
                      })()
                    }`}>
                      <span className="block text-[9px] font-bold uppercase text-rose-600">Biased Signal</span>
                      <span className={`text-xs font-bold ${
                        (() => {
                          const signal = (selectedReport.explanation as any)?.biasSignal || 'Low';
                          if (signal === 'Critical' || signal === 'High') return 'text-rose-500';
                          if (signal === 'Medium') return 'text-amber-500';
                          return 'text-emerald-500';
                        })()
                      }`}>{(selectedReport.explanation as any)?.biasSignal || 'Low'}</span>
                    </div>
                  </div>
                </div>

                {/* Integrity Proof */}
                <div className={`p-6 rounded-2xl border min-w-0 ${isDarkMode ? 'bg-[#1E293B] border-[#334155]' : 'bg-white border-[#E2E8F0] shadow-sm'}`}>
                  <h4 className="text-lg font-bold mb-4 flex items-center gap-2">
                    <svg className="w-5 h-5 text-emerald-600" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04M12 2.944a11.955 11.955 0 01-4.532 10.948m14.75 0a11.955 11.955 0 01-4.532 10.948M12 21.056c2.518 0 4.87-.775 6.818-2.112a11.955 11.955 0 01-6.818 2.112c-2.518 0-4.87-.775-6.818-2.112a11.955 11.955 0 016.818 2.112z" /></svg>
                    Integrity Proof
                  </h4>
                  {selectedReport.blockchain ? (
                    <div className="space-y-4 mono text-[10px] uppercase">
                      <div className="bg-slate-900 text-slate-300 p-4 rounded-xl border border-white/5 space-y-2 text-left">
                        <div className="flex justify-between">
                          <span className="opacity-40">Network</span>
                          <span className="text-emerald-400">{selectedReport.blockchain.network}</span>
                        </div>
                        <div className="flex flex-col gap-1">
                          <span className="opacity-40">TX_HASH</span>
                          <span className="text-emerald-400 break-all select-all font-mono">{selectedReport.blockchain.transactionHash}</span>
                        </div>
                        <div className="flex justify-between">
                          <span className="opacity-40">TIMESTAMP</span>
                          <span>{selectedReport.blockchain.timestamp || 'N/A'}</span>
                        </div>
                        <div className="pt-2 flex justify-between">
                          <span className="opacity-40">DATA_IPFS</span>
                          {selectedReport.blockchain.ipfsHash ? (
                            <span className="text-emerald-300 underline cursor-pointer select-all font-mono">
                              {selectedReport.blockchain.ipfsHash.length > 12 
                                ? `${selectedReport.blockchain.ipfsHash.substring(0, 12)}...` 
                                : selectedReport.blockchain.ipfsHash}
                            </span>
                          ) : (
                            <span>N/A</span>
                          )}
                        </div>
                      </div>
                    </div>
                  ) : (
                    <span className="text-xs opacity-50">No blockchain details available.</span>
                  )}
                </div>

              </div>
              
              <div className="flex justify-end pt-6 border-t border-slate-200/10">
                <button
                  onClick={() => setSelectedReport(null)}
                  className={`px-6 py-2.5 rounded-xl text-xs font-bold transition-all border ${
                    isDarkMode ? 'border-[#334155] text-slate-300 hover:bg-[#1E293B]' : 'border-[#E2E8F0] text-slate-700 hover:bg-slate-50'
                  }`}
                >
                  Close Details
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default PortalView;
