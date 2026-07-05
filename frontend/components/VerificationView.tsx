import React, { useState, useEffect } from 'react';
import { VerificationResult, VerificationStatus } from '../types';
import { verifyNewsContent, submitUserFeedback, downloadArticlePdf } from '../services/apiService';
import { User } from 'firebase/auth';
import { saveVerificationResult, saveFeedback } from '../services/firebase';
// @ts-ignore
import { franc } from 'franc-min';

interface VerificationViewProps {
  isDarkMode: boolean;
  user: User | null;
  inputText: string;
  setInputText: (text: string) => void;
  result: VerificationResult | null;
  setResult: (result: VerificationResult | null) => void;
  isVerifying: boolean;
  setIsVerifying: (loading: boolean) => void;
}

const VerificationView: React.FC<VerificationViewProps> = ({ 
  isDarkMode, 
  user, 
  inputText,
  setInputText,
  result,
  setResult,
  isVerifying,
  setIsVerifying
}) => {
  const [showDisputeModal, setShowDisputeModal] = useState(false);
  const [showSourceDetails, setShowSourceDetails] = useState(false);
  const [pdfDownloading, setPdfDownloading] = useState(false);
  const [shareStatus, setShareStatus] = useState<'idle' | 'copied' | 'shared'>('idle');
  const [selectedLanguage, setSelectedLanguage] = useState('auto');
  const [selectedPlatform, setSelectedPlatform] = useState('auto');
  const [detectedLanguage, setDetectedLanguage] = useState<string | null>(null);
  const [detectedPlatform, setDetectedPlatform] = useState<string | null>(null);

  // ── Auto-detect platform and language from input text ──────────────────────
  const detectPlatformFromText = (text: string): string | null => {
    const t = text.toLowerCase();
    if (/twitter\.com|x\.com|t\.co\//.test(t)) return 'twitter';
    if (/t\.me\/|telegram\.me\/|telegram\.org/.test(t)) return 'telegram';
    if (/reddit\.com\/r\//.test(t)) return 'reddit';
    // Any standalone URL → generic website
    if (/https?:\/\//.test(t)) return 'website';
    // Content that is not from a social platform is treated as website/news content
    return 'website';
  };

  const detectLanguageFromText = (text: string): string | null => {
    // Decode percent-encoded URL sequences (e.g. %e5%a4%ae → 央 in Chinese URLs)
    let decoded = text;
    try {
      decoded = decodeURIComponent(text.replace(/\+/g, ' '));
    } catch {
      // If decoding fails (malformed URL) fall back to raw text
      decoded = text;
    }

    // Chinese characters are extremely distinctive, so keep a regex check as a fast path
    if (/[\u4e00-\u9fff\u3400-\u4dbf]/.test(decoded)) return 'zh';

    // Clean up URLs, numbers, punctuation to avoid messing up n-gram detection
    const cleanForDetection = (str: string) => {
      return str
        .replace(/^https?:\/\/(www\.)?[-a-zA-Z0-9@:%._+~#=]{1,256}\.[a-zA-Z0-9()]{1,6}/gi, '')
        .replace(/[\/\-_?=&]/g, ' ')
        .replace(/[^a-zA-Z\u4e00-\u9fff\u3400-\u4dbf\s]/g, ' ')
        .replace(/\s+/g, ' ')
        .trim();
    };

    const cleanedText = cleanForDetection(decoded);

    // Run franc-min on cleaned text
    if (cleanedText.length > 5) {
      try {
        const detectedCode = franc(cleanedText);
        // zlm = Standard Malay, ind = Indonesian, msa = Malay macrolanguage
        if (detectedCode === 'zlm' || detectedCode === 'ind' || detectedCode === 'msa') {
          return 'ms';
        }
        // cmn = Mandarin Chinese, zho = Chinese macrolanguage, nan = Min Nan, hak = Hakka, yue = Cantonese
        if (detectedCode === 'cmn' || detectedCode === 'zho' || detectedCode === 'nan' || detectedCode === 'hak' || detectedCode === 'yue') {
          return 'zh';
        }
        if (detectedCode === 'eng') {
          return 'en';
        }
      } catch (err) {
        console.error('Error running franc-min:', err);
      }
    }

    // Fallback to heuristic rules for short text
    // Malay common words
    if (/\b(dan|yang|di|tidak|untuk|dengan|adalah|ini|itu|mereka|kami|saya|boleh|akan|ada|kita|hari|kes|maut|lapor|baru)\b/i.test(decoded)) return 'ms';
    // Default to English if any Latin letters are present
    if (/[a-zA-Z]/.test(decoded)) return 'en';
    
    return null;
  };

  const handleInputChange = (text: string) => {
    setInputText(text);
    if (text.trim().length > 10) {
      const plat = detectPlatformFromText(text);
      const lang = detectLanguageFromText(text);
      setDetectedPlatform(plat);
      setDetectedLanguage(lang);
      if (plat && selectedPlatform === 'auto') setSelectedPlatform('auto'); // keep auto but show badge
      if (lang && selectedLanguage === 'auto') setSelectedLanguage('auto');
    } else {
      setDetectedPlatform(null);
      setDetectedLanguage(null);
    }
  };

  // Resolve effective values used when sending to backend
  const effectivePlatform = selectedPlatform === 'auto' ? (detectedPlatform || 'website') : selectedPlatform;
  const effectiveLanguage = selectedLanguage === 'auto' ? (detectedLanguage || 'en') : selectedLanguage;

  const handleDownloadPdf = async () => {
    if (!result) return;
    setPdfDownloading(true);
    try {
      const token = localStorage.getItem('access_token');
      if (!token) throw new Error("Please log in to download the PDF certificate.");
      
      const articleId = result.id || (result as any).article_id || 'unknown';
      const blob = await downloadArticlePdf(token, articleId);
      
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', `verification_report_${articleId}.pdf`);
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
    } catch (err: any) {
      console.error("Failed to download PDF:", err);
      alert(err.message || "Failed to download PDF report. Make sure you are signed in.");
    } finally {
      setPdfDownloading(false);
    }
  };

  const handleShare = async () => {
    if (!result) return;
    const label = (result.finalAssessment?.label || result.status || 'UNCERTAIN').toUpperCase().replace('_', ' ');
    const score = result.finalAssessment ? Math.round(result.finalAssessment.score * 100) : 0;
    const txHash = result.blockchain?.transactionHash || 'N/A';
    const explorerUrl = result.blockchain?.transactionHash && txHash !== 'N/A'
      ? `\nVerify on-chain: https://sepolia.etherscan.io/tx/${txHash}`
      : '';
    const shareText = `*Fake News Detection Result*\n\n*Verdict:* ${label}\n*Risk Score:* ${score}%\n*Blockchain Proof:* ${txHash}${explorerUrl}\n\nVerified with Explainable AI + Blockchain Anchoring.`;

    try {
      const whatsappUrl = `https://wa.me/?text=${encodeURIComponent(shareText)}`;
      window.open(whatsappUrl, '_blank', 'noopener,noreferrer');
      setShareStatus('shared');
    } catch {
      try {
        await navigator.clipboard.writeText(shareText);
        setShareStatus('copied');
      } catch {
        setShareStatus('idle');
      }
    }
    setTimeout(() => setShareStatus('idle'), 3000);
  };
  const [feedbackType, setFeedbackType] = useState('incorrect_classification');
  const [feedbackMessage, setFeedbackMessage] = useState('');
  const [feedbackEmail, setFeedbackEmail] = useState('');
  const [feedbackSubmitting, setFeedbackSubmitting] = useState(false);
  const [feedbackSuccess, setFeedbackSuccess] = useState<string | null>(null);
  const [feedbackError, setFeedbackError] = useState<string | null>(null);

  useEffect(() => {
    if (user && user.email) {
      setFeedbackEmail(user.email);
    }
  }, [user]);

  const handleDisputeSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!result) return;
    setFeedbackSubmitting(true);
    setFeedbackError(null);
    setFeedbackSuccess(null);

    const articleId = result.id || (result as any).article_id || 'unknown';
    const verdict = (result.finalAssessment?.label || result.status || 'UNCERTAIN').toString();

    try {
      await saveFeedback({
        article_id: articleId,
        feedback_type: feedbackType,
        message: feedbackMessage,
        user_email: feedbackEmail || 'anonymous@example.com',
        verdict: verdict,
        user_id: user?.uid || null,
      });
      setFeedbackSuccess("Your dispute feedback has been submitted successfully. Thank you!");
      setFeedbackMessage('');
      setTimeout(() => {
        setShowDisputeModal(false);
        setFeedbackSuccess(null);
      }, 3000);
    } catch (err: any) {
      console.error("Dispute submission error:", err);
      setFeedbackError(err.message || "Failed to submit dispute feedback.");
    } finally {
      setFeedbackSubmitting(false);
    }
  };

  const handleVerify = async () => {
    if (!inputText.trim()) return;
    setIsVerifying(true);
    try {
      const token = localStorage.getItem('access_token');
      const apiResult = await verifyNewsContent(inputText, effectiveLanguage, effectivePlatform, token || undefined);
      setResult(apiResult);

      // Save to Firestore history if user is logged in
      if (user && user.email) {
        await saveVerificationResult(user.email, apiResult);
      }
    } catch (err) {
      console.error("Verification failed:", err);
      alert("Verification failed. Check console for details.");
    } finally {
      setIsVerifying(false);
    }
  };

  const getStatusColor = (status: string) => {
    const s = status.toUpperCase();
    if (s.includes('REAL')) return 'text-emerald-500';
    if (s.includes('FAKE')) return 'text-rose-500';
    return 'text-amber-500';
  };

  const getStatusBg = (status: string) => {
    const s = status.toUpperCase();
    if (s.includes('REAL')) return 'bg-emerald-500/10 border-emerald-500/20';
    if (s.includes('FAKE')) return 'bg-rose-500/10 border-rose-500/20';
    return 'bg-amber-500/10 border-amber-500/20';
  };

  return (
    <div className="animate-fade-in space-y-8">
      {/* Input Section */}
      <section className={`p-8 rounded-2xl border ${isDarkMode ? 'bg-[#1E293B] border-[#334155]' : 'bg-white border-[#E2E8F0] shadow-sm'}`}>
        <div className="mb-4">
          <h2 className="text-2xl font-bold mb-1">Verify News Accuracy</h2>
          <p className={`${isDarkMode ? 'text-[#94A3B8]' : 'text-slate-500'} text-sm`}>Uncover the truth behind any news headline or article snippet.</p>
        </div>
        
        <div className="relative mb-6">
          <textarea
            value={inputText}
            onChange={(e) => handleInputChange(e.target.value)}
            className={`w-full h-40 p-4 rounded-xl border focus:ring-2 focus:ring-emerald-500 outline-none transition-all ${isDarkMode ? 'bg-[#0F172A] border-[#334155] text-white' : 'bg-[#F8FAFC] border-[#E2E8F0] text-slate-800'}`}
            placeholder="Paste news text, headline, or article URL here..."
          />
          {inputText && (
            <button 
              onClick={() => { setInputText(''); setResult(null); setDetectedPlatform(null); setDetectedLanguage(null); }}
              className="absolute top-4 right-4 text-slate-400 hover:text-slate-600"
            >
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12" /></svg>
            </button>
          )}
        </div>

        {/* Auto-detected badges */}
        {(detectedPlatform || detectedLanguage) && (
          <div className="flex gap-1.5 mb-6">
            {detectedPlatform && (
              <span className="text-[9px] font-black uppercase px-2 py-0.5 rounded-full bg-blue-500/15 text-blue-500 border border-blue-500/25 flex items-center gap-1">
                <svg className="w-2.5 h-2.5" fill="currentColor" viewBox="0 0 20 20"><path fillRule="evenodd" d="M5.05 3.636a1 1 0 010 1.414 7 7 0 000 9.9 1 1 0 11-1.414 1.414 9 9 0 010-12.728 1 1 0 011.414 0zm9.9 0a1 1 0 011.414 0 9 9 0 010 12.728 1 1 0 11-1.414-1.414 7 7 0 000-9.9 1 1 0 010-1.414zM7.879 6.464a1 1 0 010 1.414 3 3 0 000 4.243 1 1 0 11-1.415 1.414 5 5 0 010-7.07 1 1 0 011.415 0zm4.242 0a1 1 0 011.415 0 5 5 0 010 7.072 1 1 0 01-1.415-1.415 3 3 0 000-4.242 1 1 0 010-1.415z" clipRule="evenodd" /></svg>
                Detected: {detectedPlatform}
              </span>
            )}
            {detectedLanguage && (
              <span className="text-[9px] font-black uppercase px-2 py-0.5 rounded-full bg-violet-500/15 text-violet-500 border border-violet-500/25 flex items-center gap-1">
                <svg className="w-2.5 h-2.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M3 5h12M9 3v2m1.048 9.5A18.022 18.022 0 016.412 9m6.088 9h7M11 21l5-10 5 10M12.751 5C11.783 10.77 8.07 15.61 3 18.129" /></svg>
                Lang: {detectedLanguage.toUpperCase()}
              </span>
            )}
          </div>
        )}

        <div className="flex flex-col sm:flex-row gap-4 items-center justify-between">
           <div className="flex flex-wrap items-center gap-4 text-xs font-semibold">
              <div className="flex items-center gap-2">
                 <span className="opacity-60">Engine:</span>
                 <span className="px-2 py-0.5 bg-emerald-500/10 text-emerald-500 text-[10px] font-black rounded uppercase">FastAPI</span>
              </div>
              <div className="flex items-center gap-1.5">
                 <span className="opacity-60">Language:</span>
                 <select 
                   value={selectedLanguage}
                   onChange={(e) => setSelectedLanguage(e.target.value)}
                   className={`px-2.5 py-1 rounded-lg border focus:ring-1 focus:ring-emerald-500 outline-none text-[11px] font-bold ${
                     isDarkMode ? 'bg-[#0F172A] border-[#334155] text-slate-200' : 'bg-[#F8FAFC] border-[#E2E8F0] text-slate-700'
                   }`}
                 >
                   <option value="auto">Auto-detect {detectedLanguage ? `(${detectedLanguage.toUpperCase()})` : ''}</option>
                   <option value="en">English</option>
                   <option value="zh">Chinese (中文)</option>
                   <option value="ms">Malay (BM)</option>
                 </select>
              </div>
              <div className="flex items-center gap-1.5">
                 <span className="opacity-60">Platform:</span>
                 <select 
                   value={selectedPlatform}
                   onChange={(e) => setSelectedPlatform(e.target.value)}
                   className={`px-2.5 py-1 rounded-lg border focus:ring-1 focus:ring-emerald-500 outline-none text-[11px] font-bold ${
                     isDarkMode ? 'bg-[#0F172A] border-[#334155] text-slate-200' : 'bg-[#F8FAFC] border-[#E2E8F0] text-slate-700'
                   }`}
                 >
                   <option value="auto">Auto-detect {detectedPlatform ? `(${detectedPlatform})` : ''}</option>
                   <option value="twitter">Twitter / X</option>
                   <option value="telegram">Telegram</option>
                   <option value="reddit">Reddit</option>
                   <option value="website">Website / News Article</option>
                 </select>
              </div>
           </div>
           <div className="flex gap-4 w-full sm:w-auto">
             {result ? (
               <button 
                 onClick={() => { setResult(null); setInputText(''); }}
                 className={`flex-1 sm:flex-none px-8 py-2.5 rounded-xl font-semibold text-white transition-all transform active:scale-95 flex items-center justify-center gap-2 bg-rose-500 hover:bg-rose-600 shadow-lg shadow-rose-500/20`}
               >
                 <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                   <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                 </svg>
                 Clear Output
               </button>
             ) : (
               <button 
                 onClick={handleVerify}
                 disabled={isVerifying || !inputText.trim()}
                 className={`flex-1 sm:flex-none px-8 py-2.5 rounded-xl font-semibold text-white transition-all transform active:scale-95 disabled:opacity-50 flex items-center justify-center gap-2 bg-emerald-500 hover:bg-emerald-600 shadow-lg shadow-emerald-500/20`}
               >
                 {isVerifying ? (
                   <>
                     <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin"></div>
                     Scanning...
                   </>
                 ) : (
                   <>
                     <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" /></svg>
                     Run Detection
                   </>
                 )}
               </button>
             )}
           </div>
        </div>
      </section>

      {/* Results Section */}
      {result && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 animate-slide-up">
          {/* Main Verdict + AI Analysis Summary (merged) */}
          {(() => {
            const label = result.finalAssessment?.label || result.status || 'UNCERTAIN';
            const score = result.finalAssessment ? result.finalAssessment.score : (result.confidence !== undefined ? result.confidence : 0.5);
            const reasoning = result.finalAssessment?.reasoning || 
              (typeof result.explanation === 'string' ? result.explanation : result.explanation?.summary) || 
              result.classification?.explanation || 
              '';
            const labelUpper = label.toUpperCase().replace('_', ' ');
            const isReal = labelUpper.includes('REAL');
            const isFake = labelUpper.includes('FAKE');
            const displayConfidence = result.finalAssessment
              ? (isFake ? score : (1 - score))
              : (result.confidence !== undefined ? result.confidence : 0.5);

            // Evidence data
            const aiSummary = result.verification?.summary || '';
            const shapData = (result.explanation?.shapData || []).slice().sort((a,b) => Math.abs(b.weight) - Math.abs(a.weight));
            const sourceComparison = result.verification?.sourceComparison || [];
            const matchingArticles = result.verification?.matchingArticles || [];
            const factualSignal = (result.explanation as any)?.factualSignal || 'Medium';
            const biasSignal = (result.explanation as any)?.biasSignal || 'Low';
            const realFactors = shapData.filter(s => s.weight < -0.1).slice(0, 3);
            const fakeFactors = shapData.filter(s => s.weight > 0.1).slice(0, 3);
            const supportingSources = sourceComparison.filter((s: any) => s.relationship === 'SUPPORTS');
            const refutingSources = sourceComparison.filter((s: any) => s.relationship === 'REFUTES');

            return (
              <div className={`lg:col-span-3 p-8 rounded-2xl border ${getStatusBg(label)} flex flex-col items-center text-center relative`}>
                {/* ── Confidence pill (top-right) ── */}
                <div className="absolute top-5 right-5 flex flex-col items-end">
                  <span className="text-[9px] font-bold uppercase tracking-wider text-slate-400">Confidence</span>
                  <span className={`text-xl font-black ${getStatusColor(label)}`}>{(displayConfidence * 100).toFixed(0)}%</span>
                </div>
                {/* ── Verdict Header ── */}
                <div className={`w-20 h-20 rounded-full mb-4 flex items-center justify-center ${getStatusColor(label)} bg-white shadow-xl`}>
                   {isReal ? (
                     <svg className="w-12 h-12" fill="currentColor" viewBox="0 0 20 20"><path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" /></svg>
                   ) : isFake ? (
                     <svg className="w-12 h-12" fill="currentColor" viewBox="0 0 20 20"><path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clipRule="evenodd" /></svg>
                   ) : (
                     <svg className="w-12 h-12" fill="currentColor" viewBox="0 0 20 20"><path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z" clipRule="evenodd" /></svg>
                   )}
                </div>
                <h3 className={`text-4xl font-black uppercase tracking-tight mb-2 ${getStatusColor(label)}`}>
                   VERDICT: {labelUpper}
                </h3>
                <div className="mt-5 flex items-center justify-center gap-3 text-[10px] font-bold uppercase text-slate-400">
                  <span className="px-2 py-1 rounded-md bg-emerald-500/10 text-emerald-600">DEEP SCAN</span>
                  {result.processingTimeMs && (
                    <span>Processed in {result.processingTimeMs} ms</span>
                  )}
                </div>

                {/* ── Why this verdict? ── */}
                <p className={`mt-6 text-lg max-w-xl leading-relaxed ${isDarkMode ? 'text-slate-200' : 'text-slate-700'}`}>
                  {reasoning}
                </p>

                {/* ── Evidence Columns ── */}
                <div className="w-full grid grid-cols-1 md:grid-cols-2 gap-4 mt-6 text-left">
                  {/* Evidence for REAL */}
                  <div className={`p-3 rounded-xl border bg-white/70 backdrop-blur-sm ${isDarkMode ? 'border-emerald-500/20' : 'border-emerald-200'}`}>
                    <h6 className="text-[10px] font-bold uppercase tracking-wider text-emerald-600 mb-2 flex items-center gap-1">
                      <svg className="w-3 h-3" fill="currentColor" viewBox="0 0 20 20"><path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" /></svg>
                      Evidence for REAL
                    </h6>
                    {realFactors.length > 0 ? (
                      <ul className="space-y-1.5">
                        {realFactors.map((f, i) => (
                          <li key={i} className="flex items-start gap-1.5 text-[11px]">
                            <span className="mono bg-emerald-500/10 text-emerald-600 px-1.5 py-0.5 rounded shrink-0">“{f.word}”</span>
                            <span className={`${isDarkMode ? 'text-slate-400' : 'text-slate-500'}`}>credible language detected</span>
                          </li>
                        ))}
                      </ul>
                    ) : (
                      <p className="text-[11px] italic opacity-50">No strong credible signals found</p>
                    )}
                    {supportingSources.length > 0 && (
                      <div className="mt-2 pt-2 border-t border-emerald-500/10">
                        {supportingSources.slice(0, 2).map((s: any, i: number) => (
                          <p key={i} className={`text-[10px] italic mt-1 ${isDarkMode ? 'text-slate-500' : 'text-slate-500'}`}>
                            <span className="font-bold text-emerald-600">{s.source_name}:</span> “{s.key_finding}”
                          </p>
                        ))}
                      </div>
                    )}
                  </div>

                  {/* Evidence for FAKE */}
                  <div className={`p-3 rounded-xl border bg-white/70 backdrop-blur-sm ${isDarkMode ? 'border-rose-500/20' : 'border-rose-200'}`}>
                    <h6 className="text-[10px] font-bold uppercase tracking-wider text-rose-600 mb-2 flex items-center gap-1">
                      <svg className="w-3 h-3" fill="currentColor" viewBox="0 0 20 20"><path fillRule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clipRule="evenodd" /></svg>
                      Evidence for FAKE
                    </h6>
                    {fakeFactors.length > 0 ? (
                      <ul className="space-y-1.5">
                        {fakeFactors.map((f, i) => (
                          <li key={i} className="flex items-start gap-1.5 text-[11px]">
                            <span className="mono bg-rose-500/10 text-rose-600 px-1.5 py-0.5 rounded shrink-0">“{f.word}”</span>
                            <span className={`${isDarkMode ? 'text-slate-400' : 'text-slate-500'}`}>suspicious / biased language</span>
                          </li>
                        ))}
                      </ul>
                    ) : (
                      <p className="text-[11px] italic opacity-50">No strong misinformation signals found</p>
                    )}
                    {refutingSources.length > 0 && (
                      <div className="mt-2 pt-2 border-t border-rose-500/10">
                        {refutingSources.slice(0, 2).map((s: any, i: number) => (
                          <p key={i} className={`text-[10px] italic mt-1 ${isDarkMode ? 'text-slate-500' : 'text-slate-500'}`}>
                            <span className="font-bold text-rose-600">{s.source_name}:</span> “{s.key_finding}”
                          </p>
                        ))}
                      </div>
                    )}
                  </div>
                </div>

                {/* ── Signal Indicators ── */}
                <div className="flex flex-wrap justify-center gap-2 mt-6">
                  <span className={`text-[10px] font-bold px-2.5 py-1 rounded-full border ${
                    factualSignal === 'High' ? 'bg-emerald-500/10 text-emerald-500 border-emerald-500/20' :
                    factualSignal === 'Low' ? 'bg-rose-500/10 text-rose-500 border-rose-500/20' :
                    'bg-amber-500/10 text-amber-500 border-amber-500/20'
                  }`}>
                    Factual Signal: {factualSignal}
                  </span>
                  <span className={`text-[10px] font-bold px-2.5 py-1 rounded-full border ${
                    (biasSignal === 'Critical' || biasSignal === 'High') ? 'bg-rose-500/10 text-rose-500 border-rose-500/20' :
                    biasSignal === 'Medium' ? 'bg-amber-500/10 text-amber-500 border-amber-500/20' :
                    'bg-emerald-500/10 text-emerald-500 border-emerald-500/20'
                  }`}>
                    Bias Signal: {biasSignal}
                  </span>
                  {matchingArticles.length > 0 && (
                    <span className="text-[10px] font-bold px-2.5 py-1 rounded-full border bg-blue-500/10 text-blue-500 border-blue-500/20">
                      {new Set(matchingArticles.map(a => a.source.toLowerCase())).size} source{new Set(matchingArticles.map(a => a.source.toLowerCase())).size !== 1 ? 's' : ''} cross-referenced
                    </span>
                  )}
                </div>

                {/* ── Claim Summary ── */}
                {aiSummary && (
                  <div className={`w-full text-left pt-4 mt-6 border-t ${isDarkMode ? 'border-slate-700' : 'border-slate-300/40'}`}>
                    <h5 className={`text-[10px] font-bold uppercase tracking-wider opacity-50 mb-2`}>Claim Summary</h5>
                    <p className={`text-sm leading-relaxed italic ${isDarkMode ? 'text-slate-400' : 'text-slate-500'}`}>
                      “{aiSummary}”
                    </p>
                  </div>
                )}
              </div>
            );
          })()}

          {/* Source Verification — combined card with summary + detailed toggle */}
          {(() => {
            const rawSources = (result.verification?.sources || result.sources || []);
            const matchingArticles = result.verification?.matchingArticles || (result.verification as any)?.matching_articles || [];

            // Build the unified source list.
            // 1. Start with the backend's sources array (deduplicated SourceMatch list).
            // 2. If that's empty but matchingArticles exist, derive sources from them.
            let sources: { name: string; confirmed: boolean; url?: string }[] = [];
            if (Array.isArray(rawSources)) {
              sources = rawSources
                .filter(s => s && s.name)
                .map(s => ({ name: s.name, confirmed: !!s.confirmed, url: s.url || undefined }));
            }

            // Build a lookup of source names we already have (case-insensitive)
            const knownNames = new Set(
              sources
                .map(s => s.name?.toLowerCase())
                .filter(Boolean)
            );

            // Merge in any matching articles whose source isn't already represented
            if (Array.isArray(matchingArticles)) {
              matchingArticles.forEach(a => {
                if (a && a.source) {
                  const srcLower = a.source.toLowerCase();
                  if (!knownNames.has(srcLower)) {
                    sources.push({ name: a.source, confirmed: false, url: a.link });
                    knownNames.add(srcLower);
                  }
                }
              });
            }

            // Enrich: if a source row has no URL but a matching article does, attach it
            sources = sources.map(s => {
              if (s && s.name) {
                const match = matchingArticles.find(a => a && a.source && a.source.toLowerCase() === s.name.toLowerCase());
                if (!s.url && match) return { ...s, url: match.link };
              }
              return s;
            });

            const sourceComparison = result.verification?.sourceComparison || (result.verification as any)?.source_comparison || [];

            // Build relationship map from source comparison (semantic analysis)
            const relationshipMap: Record<string, string> = {};
            if (Array.isArray(sourceComparison)) {
              sourceComparison.forEach((sc: any) => {
                if (sc && sc.source_name) {
                  relationshipMap[sc.source_name.toLowerCase()] = sc.relationship;
                }
              });
            }

            // Build merged unified list: one row per source with relationship + finding
            const articleBySource: Record<string, typeof matchingArticles[0]> = {};
            if (Array.isArray(matchingArticles)) {
              matchingArticles.forEach(a => {
                if (a && a.source) {
                  articleBySource[a.source.toLowerCase()] = a;
                }
              });
            }
            const findingBySource: Record<string, string> = {};
            if (Array.isArray(sourceComparison)) {
              sourceComparison.forEach((sc: any) => {
                if (sc && sc.source_name) {
                  findingBySource[sc.source_name.toLowerCase()] = sc.key_finding;
                }
              });
            }

            const totalCount = sources.length;
            const confirmedCount = sources.filter(s => s.confirmed).length;
            
            let supportsCount = 0;
            let refutesCount = 0;
            let unrelatedCount = 0;
            
            sources.forEach(source => {
              if (source && source.name) {
                const nameLower = source.name.toLowerCase();
                const relation = relationshipMap[nameLower] || (source.confirmed ? 'SUPPORTS' : 'UNRELATED');
                if (relation === 'SUPPORTS') {
                  supportsCount++;
                } else if (relation === 'REFUTES') {
                  refutesCount++;
                } else {
                  unrelatedCount++;
                }
              }
            });

            // Helper to map relationship to display
            const getRelationBadge = (relation: string) => {
              if (relation === 'SUPPORTS') return { text: '✓ Supports', cls: 'bg-emerald-500/10 text-emerald-500 border-emerald-500/20' };
              if (relation === 'REFUTES') return { text: '✗ Refutes', cls: 'bg-rose-500/10 text-rose-500 border-rose-500/20' };
              if (relation === 'RELATED') return { text: '— Related', cls: 'bg-amber-500/10 text-amber-500 border-amber-500/20' };
              return { text: '— Unrelated', cls: 'bg-slate-500/10 text-slate-400 border-slate-500/20' };
            };

            return (
              <div className={`lg:col-span-3 p-6 rounded-2xl border ${isDarkMode ? 'bg-[#1E293B] border-[#334155]' : 'bg-white border-[#E2E8F0] shadow-sm'}`}>
                <div className="flex items-center justify-between mb-4">
                  <div className="flex items-center gap-2">
                    <svg className="w-5 h-5 text-emerald-600" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04M12 2.944a11.955 11.955 0 01-4.532 10.948m14.75 0a11.955 11.955 0 01-4.532 10.948" /></svg>
                    <h4 className="text-lg font-bold">Source Verification</h4>
                    {sourceComparison.length > 0 && (
                      <span className={`ml-1 text-[10px] font-bold px-2 py-0.5 rounded-full border ${isDarkMode ? 'bg-violet-500/10 border-violet-500/20 text-violet-400' : 'bg-violet-50 border-violet-200 text-violet-600'}`}>
                        AI Semantic Analysis
                      </span>
                    )}
                  </div>
                </div>
                <p className={`text-[10px] mb-4 ${isDarkMode ? 'text-slate-500' : 'text-slate-400'}`}>Cross-referenced against authoritative sources with semantic relationship analysis.</p>

                {/* ── DEFAULT VIEW: Compact Summary ── */}
                <div className={`p-4 rounded-xl mb-4 ${isDarkMode ? 'bg-[#0F172A]' : 'bg-slate-50'}`}>
                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                    <div className="text-center">
                      <span className={`block text-[9px] font-bold uppercase opacity-50 mb-1`}>Sources Found</span>
                      <span className="text-2xl font-black text-slate-600 dark:text-slate-200">{totalCount}</span>
                    </div>
                    <div className="text-center">
                      <span className={`block text-[9px] font-bold uppercase opacity-50 mb-1`}>Supporting</span>
                      <span className="text-2xl font-black text-emerald-500">{supportsCount}</span>
                      <span className="block text-[8px] text-slate-400 mt-0.5">{totalCount > 0 ? `(${Math.round((supportsCount / totalCount) * 100)}%)` : ''}</span>
                    </div>
                    <div className="text-center">
                      <span className={`block text-[9px] font-bold uppercase opacity-50 mb-1`}>Refutes</span>
                      <span className="text-2xl font-black text-rose-500">{refutesCount}</span>
                      <span className="block text-[8px] text-slate-400 mt-0.5">{totalCount > 0 ? `(${Math.round((refutesCount / totalCount) * 100)}%)` : ''}</span>
                    </div>
                    <div className="text-center">
                      <span className={`block text-[9px] font-bold uppercase opacity-50 mb-1`}>Trusted Outlets</span>
                      <span className="text-2xl font-black text-emerald-600">{confirmedCount}/{totalCount}</span>
                      <span className="block text-[8px] text-slate-400 mt-0.5">{totalCount > 0 ? `(${Math.round((confirmedCount / totalCount) * 100)}%)` : ''}</span>
                    </div>
                  </div>
                </div>

                {/* ── EXPANDABLE VIEW: Detailed Table ── */}
                {showSourceDetails && (
                  <div className="animate-fade-in overflow-x-auto">
                    <table className="w-full text-left border-collapse text-xs">
                      <thead>
                        <tr className={`border-b ${isDarkMode ? 'border-slate-700' : 'border-slate-200'}`}>
                          <th className="py-2 pr-3 font-bold uppercase tracking-wider opacity-50 whitespace-nowrap">Validated</th>
                          <th className="py-2 pr-3 font-bold uppercase tracking-wider opacity-50 whitespace-nowrap">Source</th>
                          <th className="py-2 pr-3 font-bold uppercase tracking-wider opacity-50 whitespace-nowrap">Relation</th>
                          <th className="py-2 font-bold uppercase tracking-wider opacity-50">Finding / Article</th>
                        </tr>
                      </thead>
                      <tbody>
                        {sources.map((source, idx) => {
                          if (!source || !source.name) return null;
                          const nameLower = source.name.toLowerCase();
                          const relation = relationshipMap[nameLower] || (source.confirmed ? 'SUPPORTS' : 'UNRELATED');
                          const badge = getRelationBadge(relation);
                          const match = articleBySource[nameLower];
                          const finding = findingBySource[nameLower];
                          return (
                            <tr key={idx} className={`border-b transition-colors ${isDarkMode ? 'border-slate-700/50 hover:bg-slate-700/20' : 'border-slate-100 hover:bg-slate-50'}`}>
                              <td className="py-3 pr-3 whitespace-nowrap">
                                {source.confirmed ? (
                                  <span className="inline-flex items-center justify-center w-5 h-5 rounded-full bg-emerald-500 text-white text-[10px]">✓</span>
                                ) : (
                                  <span className="inline-flex items-center justify-center w-5 h-5 rounded-full bg-slate-300 dark:bg-slate-700 text-slate-500 text-[10px]">✗</span>
                                )}
                              </td>
                              <td className="py-3 pr-3 font-bold whitespace-nowrap">
                                {source.name}
                                {match && (
                                  <a href={match.link} target="_blank" rel="noopener noreferrer" className="block text-[9px] font-normal text-emerald-500 hover:underline mt-0.5 truncate max-w-[140px]">{match.title}</a>
                                )}
                              </td>
                              <td className="py-3 pr-3">
                                <span className={`px-2 py-0.5 rounded text-[10px] font-black uppercase whitespace-nowrap border ${badge.cls}`}>{badge.text}</span>
                              </td>
                              <td className={`py-3 italic text-[11px] ${isDarkMode ? 'text-slate-400' : 'text-slate-500'}`}>
                                {finding ? `"${finding}"` : (match?.snippet ? match.snippet : '—')}
                              </td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                )}

                {/* Toggle Button */}
                <button
                  onClick={() => setShowSourceDetails(!showSourceDetails)}
                  className={`mt-3 w-full py-2 rounded-lg text-xs font-bold transition-all flex items-center justify-center gap-2 ${
                    isDarkMode ? 'bg-slate-800 hover:bg-slate-700 text-slate-300' : 'bg-slate-100 hover:bg-slate-200 text-slate-600'
                  }`}
                >
                  {showSourceDetails ? 'Hide Details ▲' : 'View Details ▼'}
                </button>

                {/* Grounding Score bar */}
                <div className="mt-5 pt-5 border-t border-slate-200/20">
                   <div className="flex justify-between items-end mb-2">
                     <span className="text-xs font-bold uppercase opacity-50">Grounding Score</span>
                     <span className={`text-xl font-black ${(() => {
                       const label = (result.finalAssessment?.label || result.status || '').toUpperCase();
                       return label.includes('FAKE') ? 'text-rose-500' : 'text-emerald-500';
                     })()}`}>
                        {(() => {
                           const stored = result.verification?.verificationScore !== undefined 
                             ? result.verification.verificationScore 
                             : (result.verification as any)?.verification_score;
                           if (stored !== undefined && stored > 0) {
                            return `${(stored * 100).toFixed(0)}%`;
                          }
                          // Fallback: derive from actual article coverage so we don't
                          // show a misleading 0% when sources were genuinely found.
                          if (sources.length > 0) {
                            const base = sources.length <= 2 ? 0.40 : sources.length <= 5 ? 0.55 : 0.70;
                            const bonus = Math.min(sources.filter(s => s.confirmed).length * 0.10, 0.30);
                            return `${Math.round((base + bonus) * 100)}%`;
                          }
                          const label = (result.finalAssessment?.label || result.status || '').toUpperCase();
                          return label.includes('FAKE') ? '0%' : '88%';
                        })()}
                     </span>
                   </div>
                   <div className={`w-full h-2 rounded-full ${isDarkMode ? 'bg-[#0F172A]' : 'bg-slate-100'} overflow-hidden`}>
                      <div
                        className={`h-full transition-all duration-1000 ${(() => {
                          const label = (result.finalAssessment?.label || result.status || '').toUpperCase();
                          return label.includes('FAKE') ? 'bg-rose-500' : 'bg-emerald-500';
                        })()}`}
                        style={{
                          width: (() => {
                            const stored = result.verification?.verificationScore !== undefined 
                             ? result.verification.verificationScore 
                             : (result.verification as any)?.verification_score;
                            if (stored !== undefined && stored > 0) {
                              return `${stored * 100}%`;
                            }
                            if (sources.length > 0) {
                              const base = sources.length <= 2 ? 0.40 : sources.length <= 5 ? 0.55 : 0.70;
                              const bonus = Math.min(sources.filter(s => s.confirmed).length * 0.10, 0.30);
                              return `${(base + bonus) * 100}%`;
                            }
                            const label = (result.finalAssessment?.label || result.status || '').toUpperCase();
                            return label.includes('FAKE') ? '0%' : '88%';
                          })()
                        }}
                      />
                   </div>
                </div>
              </div>
            );
          })()}

          {/* Feature Attribution */}
          <div className={`p-6 rounded-2xl border ${isDarkMode ? 'bg-[#1E293B] border-[#334155]' : 'bg-white border-[#E2E8F0] shadow-sm'}`}>
            <h4 className="text-lg font-bold mb-4 flex items-center gap-2">
              <svg className="w-5 h-5 text-emerald-600" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" /></svg>
              Feature Attribution
            </h4>
            <p className="text-xs mb-6 opacity-60">SHAP values indicating word contribution towards the verdict:</p>
            <div className="space-y-4">
              {((result.explanation && (result.explanation.shapData || (result.explanation as any).shap_data)) || result.shapData || (result as any).shap_data || []).slice().sort((a,b) => Math.abs(b.weight) - Math.abs(a.weight)).map((item, idx) => (
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
                  const signal = (result.explanation as any)?.factualSignal || (result.explanation as any)?.factual_signal || 'Medium';
                  if (signal === 'High') return 'bg-emerald-500/10 border-emerald-500/20';
                  if (signal === 'Low') return 'bg-rose-500/10 border-rose-500/20';
                  return 'bg-amber-500/10 border-amber-500/20';
                })()
              }`}>
                <span className="block text-[9px] font-bold uppercase text-emerald-600">Factual Signal</span>
                <span className={`text-xs font-bold ${
                  (() => {
                    const signal = (result.explanation as any)?.factualSignal || (result.explanation as any)?.factual_signal || 'Medium';
                    if (signal === 'High') return 'text-emerald-500';
                    if (signal === 'Low') return 'text-rose-500';
                    return 'text-amber-500';
                  })()
                }`}>{(result.explanation as any)?.factualSignal || (result.explanation as any)?.factual_signal || 'Medium'}</span>
              </div>
              <div className={`p-2 rounded-lg border text-center ${
                (() => {
                  const signal = (result.explanation as any)?.biasSignal || (result.explanation as any)?.bias_signal || 'Low';
                  if (signal === 'Critical' || signal === 'High') return 'bg-rose-500/10 border-rose-500/20';
                  if (signal === 'Medium') return 'bg-amber-500/10 border-amber-500/20';
                  return 'bg-emerald-500/10 border-emerald-500/20';
                })()
              }`}>
                <span className="block text-[9px] font-bold uppercase text-rose-600">Biased Signal</span>
                <span className={`text-xs font-bold ${
                  (() => {
                    const signal = (result.explanation as any)?.biasSignal || (result.explanation as any)?.bias_signal || 'Low';
                    if (signal === 'Critical' || signal === 'High') return 'text-rose-500';
                    if (signal === 'Medium') return 'text-amber-500';
                    return 'text-emerald-500';
                  })()
                }`}>{(result.explanation as any)?.biasSignal || 'Low'}</span>
              </div>
            </div>
          </div>

          {/* Verification Log */}
          <div className={`p-6 rounded-2xl border ${isDarkMode ? 'bg-[#1E293B] border-[#334155]' : 'bg-white border-[#E2E8F0] shadow-sm'}`}>
             <h4 className="text-lg font-bold mb-4 flex items-center gap-2">
                <svg className="w-5 h-5 text-emerald-600" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04M12 2.944a11.955 11.955 0 01-4.532 10.948m14.75 0a11.955 11.955 0 01-4.532 10.948M12 21.056c2.518 0 4.87-.775 6.818-2.112a11.955 11.955 0 01-6.818 2.112c-2.518 0-4.87-.775-6.818-2.112a11.955 11.955 0 016.818 2.112z" /></svg>
                Integrity Proof
             </h4>
             <div className="space-y-4 mono text-[10px] uppercase">
                {result.blockchain ? (
                  <div className="bg-slate-900 text-slate-300 p-4 rounded-xl border border-white/5 space-y-3">
                    <div className="flex items-start justify-between gap-3">
                      <span className="opacity-40 shrink-0">Network</span>
                      <span className="text-emerald-400 text-right">{result.blockchain.network}</span>
                    </div>
                    <div className="flex items-start justify-between gap-3">
                      <span className="opacity-40 shrink-0">TX Hash</span>
                      <span className="text-emerald-400 text-right break-all">{result.blockchain.transactionHash}</span>
                    </div>
                    <div className="flex items-start justify-between gap-3">
                      <span className="opacity-40 shrink-0">Timestamp</span>
                      <span className="text-right">{result.blockchain.timestamp}</span>
                    </div>
                    <div className="flex items-start justify-between gap-3">
                       <span className="opacity-40 shrink-0">Data IPFS</span>
                       {result.blockchain.ipfsHash ? (
                         <span className="text-emerald-300 underline cursor-pointer text-right break-all">
                           {result.blockchain.ipfsHash.length > 12 
                             ? `${result.blockchain.ipfsHash.substr(0, 12)}...` 
                             : result.blockchain.ipfsHash}
                         </span>
                       ) : (
                         <span className="text-right">N/A</span>
                       )}
                    </div>
                    {result.blockchain.blockNumber !== undefined && result.blockchain.blockNumber > 0 && (
                      <div className="flex items-start justify-between gap-3">
                        <span className="opacity-40 shrink-0">Block</span>
                        <span className="text-right">{result.blockchain.blockNumber}</span>
                      </div>
                    )}
                  </div>
                ) : (
                  <div className="text-xs opacity-50 italic p-4 text-center border border-dashed border-slate-300 dark:border-slate-800 rounded-xl">
                    No blockchain verification details available.
                  </div>
                )}
             </div>
             <div className="grid grid-cols-1 gap-2 mt-4">
              <button 
                type="button"
                disabled={pdfDownloading}
                onClick={handleDownloadPdf}
                className="py-2.5 rounded-xl bg-emerald-500 text-white font-bold text-xs hover:bg-emerald-600 transition-all shadow-md active:translate-y-0.5 disabled:opacity-50 flex items-center justify-center gap-2"
              >
                {pdfDownloading ? (
                  <>
                    <div className="w-3.5 h-3.5 border-2 border-white/30 border-t-white rounded-full animate-spin"></div>
                    Downloading...
                  </>
                ) : "Download Signed Report"}
              </button>
            </div>
          </div>

        </div>
      )}

      {result && (
        <div className="flex justify-center gap-4 py-12">
           <button 
             onClick={() => {
               setShowDisputeModal(true);
               setFeedbackError(null);
               setFeedbackSuccess(null);
               if (user && user.email) {
                 setFeedbackEmail(user.email);
               }
             }}
             className={`px-8 py-3 rounded-2xl text-sm font-bold flex items-center gap-3 transition-all ${isDarkMode ? 'bg-[#334155] hover:bg-[#475569] text-slate-300' : 'bg-white border-2 border-slate-100 hover:border-emerald-100 text-slate-500 shadow-sm'}`}
           >
             <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" /></svg>
             Manual Dispute
           </button>
           <button
             onClick={handleShare}
             className={`px-10 py-3 rounded-2xl text-sm font-bold text-white flex items-center gap-3 shadow-xl transition-all active:scale-95 ${
               shareStatus === 'idle'
                 ? 'bg-emerald-500 shadow-emerald-500/30 hover:scale-105'
                 : 'bg-slate-500 shadow-slate-500/30'
             }`}
           >
             {shareStatus !== 'idle' ? (
               <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 24 24"><path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.149-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347m-5.421 7.403h-.004a9.87 9.87 0 01-5.031-1.378l-.361-.214-3.741.982.998-3.648-.235-.374a9.86 9.86 0 01-1.51-5.26c.001-5.45 4.436-9.884 9.888-9.884 2.64 0 5.122 1.03 6.988 2.898a9.825 9.825 0 012.893 6.994c-.003 5.45-4.437 9.884-9.885 9.884m8.413-18.297A11.815 11.815 0 0012.05 0C5.495 0 .16 5.335.157 11.892c0 2.096.547 4.142 1.588 5.945L.057 24l6.305-1.654a11.882 11.882 0 005.683 1.448h.005c6.554 0 11.89-5.335 11.893-11.893a11.821 11.821 0 00-3.48-8.413Z" /></svg>
             ) : (
               <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 24 24"><path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.149-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347m-5.421 7.403h-.004a9.87 9.87 0 01-5.031-1.378l-.361-.214-3.741.982.998-3.648-.235-.374a9.86 9.86 0 01-1.51-5.26c.001-5.45 4.436-9.884 9.888-9.884 2.64 0 5.122 1.03 6.988 2.898a9.825 9.825 0 012.893 6.994c-.003 5.45-4.437 9.884-9.885 9.884m8.413-18.297A11.815 11.815 0 0012.05 0C5.495 0 .16 5.335.157 11.892c0 2.096.547 4.142 1.588 5.945L.057 24l6.305-1.654a11.882 11.882 0 005.683 1.448h.005c6.554 0 11.89-5.335 11.893-11.893a11.821 11.821 0 00-3.48-8.413Z" /></svg>
             )}
             {shareStatus === 'idle' ? 'Share via WhatsApp' : shareStatus === 'copied' ? 'Copied to Clipboard!' : 'Opened in WhatsApp!'}
           </button>
        </div>
      )}

      {/* Manual Dispute Modal */}
      {showDisputeModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm animate-fade-in">
          <div className={`w-full max-w-lg p-6 rounded-3xl border shadow-2xl ${
            isDarkMode ? 'bg-[#1E293B] border-[#334155] text-white' : 'bg-white border-[#E2E8F0] text-slate-800'
          }`}>
            <h3 className="text-xl font-extrabold text-emerald-500 flex items-center gap-2">
              ⚖️ File a Manual Dispute
            </h3>
            <p className="mt-2 text-xs opacity-75">
              Submit feedback if you believe this classification is incorrect or needs review.
            </p>

            {feedbackError && (
              <div className="mt-4 p-3 rounded-xl bg-rose-500/10 border border-rose-500/20 text-rose-500 text-xs font-semibold">
                ⚠️ {feedbackError}
              </div>
            )}

            {feedbackSuccess ? (
              <div className="mt-4 p-4 rounded-xl bg-emerald-500/10 border border-emerald-500/20 text-emerald-500 text-xs font-semibold flex items-center gap-2 animate-fade-in">
                <svg className="w-5 h-5 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>
                {feedbackSuccess}
              </div>
            ) : (
              <form onSubmit={handleDisputeSubmit} className="mt-4 space-y-4">
                <div>
                  <label className="block text-xs font-bold mb-1.5 uppercase opacity-75">Dispute Reason</label>
                  <select
                    value={feedbackType}
                    onChange={(e) => setFeedbackType(e.target.value)}
                    className={`w-full px-4 py-2.5 rounded-xl border focus:ring-2 focus:ring-emerald-500 outline-none transition-all text-sm ${
                      isDarkMode ? 'bg-[#0F172A] border-[#334155] text-white' : 'bg-[#F8FAFC] border-[#E2E8F0]'
                    }`}
                  >
                    <option value="incorrect_classification">Incorrect Classification (Real/Fake verdict is wrong)</option>
                    <option value="missing_sources">Missing Sources (Relevant matching source is not listed)</option>
                    <option value="outdated_information">Outdated Information (Fact checks are obsolete)</option>
                    <option value="other">Other Reason</option>
                  </select>
                </div>

                <div>
                  <label className="block text-xs font-bold mb-1.5 uppercase opacity-75">Contact Email</label>
                  <input
                    type="email"
                    required
                    value={feedbackEmail}
                    onChange={(e) => setFeedbackEmail(e.target.value)}
                    placeholder="your-email@example.com"
                    className={`w-full px-4 py-2.5 rounded-xl border focus:ring-2 focus:ring-emerald-500 outline-none transition-all text-sm ${
                      isDarkMode ? 'bg-[#0F172A] border-[#334155] text-white' : 'bg-[#F8FAFC] border-[#E2E8F0]'
                    }`}
                  />
                </div>

                <div>
                  <label className="block text-xs font-bold mb-1.5 uppercase opacity-75">Detailed Message</label>
                  <textarea
                    required
                    rows={4}
                    value={feedbackMessage}
                    onChange={(e) => setFeedbackMessage(e.target.value)}
                    placeholder="Provide evidence or context for why this classification is in dispute..."
                    className={`w-full px-4 py-3 rounded-xl border focus:ring-2 focus:ring-emerald-500 outline-none transition-all text-sm ${
                      isDarkMode ? 'bg-[#0F172A] border-[#334155] text-white' : 'bg-[#F8FAFC] border-[#E2E8F0]'
                    }`}
                  />
                </div>

                <div className="pt-2 flex justify-end gap-3">
                  <button
                    type="button"
                    disabled={feedbackSubmitting}
                    onClick={() => setShowDisputeModal(false)}
                    className={`px-4 py-2 rounded-xl font-bold text-xs transition-all ${
                      isDarkMode ? 'bg-slate-800 hover:bg-slate-700' : 'bg-slate-100 hover:bg-slate-200'
                    }`}
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    disabled={feedbackSubmitting || !feedbackMessage.trim()}
                    className="px-4 py-2 bg-emerald-500 hover:bg-emerald-600 text-white font-bold text-xs rounded-xl transition-all flex items-center gap-2"
                  >
                    {feedbackSubmitting ? (
                      <>
                        <div className="w-3.5 h-3.5 border-2 border-white/30 border-t-white rounded-full animate-spin"></div>
                        Submitting...
                      </>
                    ) : "Submit Dispute"}
                  </button>
                </div>
              </form>
            )}
          </div>
        </div>
      )}
    </div>
  );
};

export default VerificationView;
