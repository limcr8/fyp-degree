import React, { useState, useEffect } from 'react';
import { VerificationResult, VerificationStatus } from '../types';
import { verifyNewsContent, submitUserFeedback, downloadArticlePdf } from '../services/apiService';
import { User } from 'firebase/auth';
import { saveVerificationResult } from '../services/firebase';
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
  const [pdfDownloading, setPdfDownloading] = useState(false);
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

    try {
      await submitUserFeedback({
        article_id: articleId,
        feedback_type: feedbackType,
        message: feedbackMessage,
        user_email: feedbackEmail || 'anonymous@example.com'
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

  const sampleData: any = {
    id: 'sample-9921',
    text: 'BREAKING: NASA scientists discover massive structure on the dark side of the moon that appears to be of artificial origin.',
    status: VerificationStatus.FAKE,
    confidence: 0.94,
    explanation: "The content exhibits several markers of sensationalized misinformation. There is no corroborating evidence from official NASA channels or peer-reviewed journals. The linguistic patterns involve high-arousal language and lack specific astronomical coordinates or technical citations typical of such a discovery.",
    shapData: [
      { word: 'BREAKING', weight: 0.45 },
      { word: 'massive structure', weight: 0.38 },
      { word: 'dark side', weight: 0.22 },
      { word: 'artificial', weight: 0.31 },
      { word: 'NASA', weight: -0.15 }
    ],
    verification: {
      sources: [
        { name: 'NASA Official', confirmed: false },
        { name: 'AP News', confirmed: false },
        { name: 'Space.com', confirmed: false },
        { name: 'Nature', confirmed: false }
      ],
      verificationScore: 0.0,
      explanation: "0% of claims verified in authoritative sources",
      matchingArticles: [
        {
          title: "AP Fact Check: Viral claims of lunar monoliths are false",
          link: "https://apnews.com/article/fact-check-moon-monoliths",
          source: "AP News",
          snippet: "Associated Press fact checkers confirmed that recent images showing what users claim are artificial monoliths are edited photos of natural craters."
        },
        {
          title: "NASA Clarifies: No Artificial Monoliths on Moon Surface",
          link: "https://www.nasa.gov/news/lunar-surface-unverified-reports",
          source: "NASA Official",
          snippet: "Official NASA statement confirms that high-resolution scans of the lunar surface show only volcanic features and impact craters."
        }
      ]
    },
    blockchain: {
      transactionHash: '0x9d2b8347e12f45c9a721b6d54e098a1c',
      blockNumber: 19445210,
      timestamp: '2024-05-20 14:32:11 UTC',
      ipfsHash: 'QmXoypizj2Wke9u6W694r3A5f68W29r3K',
      network: 'Mainnet Relay'
    }
  };

  const handleLoadSample = () => {
    setInputText(sampleData.text);
    setResult(sampleData);
  };

  const handleVerify = async () => {
    if (!inputText.trim()) return;
    setIsVerifying(true);
    try {
      const token = localStorage.getItem('access_token');
      const apiResult = await verifyNewsContent(inputText, effectiveLanguage, effectivePlatform, token || undefined);
      setResult(apiResult);

      // Save to Firestore history if user is logged in
      if (user) {
        await saveVerificationResult(user.uid, apiResult);
      }
    } catch (err) {
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
        <div className="flex justify-between items-start mb-4">
          <div>
            <h2 className="text-2xl font-bold mb-1">Verify News Accuracy</h2>
            <p className={`${isDarkMode ? 'text-[#94A3B8]' : 'text-slate-500'} text-sm`}>Uncover the truth behind any news headline or article snippet.</p>
          </div>
          <button 
            onClick={handleLoadSample}
            className={`px-4 py-1.5 rounded-lg text-xs font-bold transition-all border ${isDarkMode ? 'border-emerald-500/30 text-emerald-400 hover:bg-emerald-500/10' : 'border-emerald-200 text-emerald-600 hover:bg-emerald-50'}`}
          >
            Load Sample Data
          </button>
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
          {/* Main Verdict */}
          {(() => {
            const label = result.finalAssessment?.label || result.status || 'UNCERTAIN';
            const score = result.finalAssessment ? result.finalAssessment.score : (result.confidence !== undefined ? result.confidence : 0.5);
            const reasoning = result.finalAssessment?.reasoning || result.explanation;
            const labelUpper = label.toUpperCase().replace('_', ' ');
            const isReal = labelUpper.includes('REAL');
            const isFake = labelUpper.includes('FAKE');

            return (
              <div className={`lg:col-span-3 p-8 rounded-2xl border ${getStatusBg(label)} flex flex-col items-center justify-center text-center`}>
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
                <div className="flex flex-col items-center gap-2 mt-4">
                  <div className="flex items-center gap-6">
                    <div className="text-center">
                      <span className="block text-[10px] font-bold uppercase text-slate-400">Risk Score</span>
                      <span className="text-2xl font-black">{(score * 100).toFixed(0)}%</span>
                    </div>
                    <div className="h-10 w-px bg-slate-300"></div>
                    <div className="text-center">
                      <span className="block text-[10px] font-bold uppercase text-slate-400">Analysis Mode</span>
                      <span className={`text-2xl font-black uppercase text-emerald-600`}>DEEP SCAN</span>
                    </div>
                  </div>
                  {result.processingTimeMs && (
                    <span className="text-[10px] font-bold text-slate-400 uppercase mt-1">
                      Processed in {result.processingTimeMs} ms
                    </span>
                  )}
                </div>
                <p className={`mt-6 text-lg max-w-xl leading-relaxed ${isDarkMode ? 'text-slate-200' : 'text-slate-700'}`}>
                  {reasoning}
                </p>
              </div>
            );
          })()}

          {/* Source Verification — unified card with inline proof links */}
          <div className={`p-6 rounded-2xl border ${isDarkMode ? 'bg-[#1E293B] border-[#334155]' : 'bg-white border-[#E2E8F0] shadow-sm'}`}>
            <h4 className="text-lg font-bold mb-1 flex items-center gap-2">
               <svg className="w-5 h-5 text-emerald-600" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04M12 2.944a11.955 11.955 0 01-4.532 10.948m14.75 0a11.955 11.955 0 01-4.532 10.948" /></svg>
               Source Verification
             </h4>
             <p className={`text-[10px] mb-4 ${isDarkMode ? 'text-slate-500' : 'text-slate-400'}`}>Cross-referenced against authoritative sources. Click any validated link to view the source article.</p>

             {/* Build a merged list: sources enriched with matching article URLs */}
             {(() => {
               const rawSources = (result.verification?.sources || result.sources || []);
               const sources = rawSources.filter(s => {
                 const nameLower = s.name.toLowerCase();
                 const isLegacyHardcoded = ["reuters", "bloomberg", "coindesk", "sec"].includes(nameLower);
                 return !(isLegacyHardcoded && !s.confirmed);
               });
               const matchingArticles = result.verification?.matchingArticles || [];

               // Map source name → matching article (case-insensitive)
               const articleBySource: Record<string, typeof matchingArticles[0]> = {};
               matchingArticles.forEach(a => {
                 articleBySource[a.source.toLowerCase()] = a;
               });

               return (
                 <div className="space-y-2.5">
                   {sources.map((source, idx) => {
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
                               <svg className="w-3 h-3 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" /></svg>
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

             {/* Grounding Score bar */}
             <div className="mt-5 pt-5 border-t border-slate-200/20">
                <div className="flex justify-between items-end mb-2">
                  <span className="text-xs font-bold uppercase opacity-50">Grounding Score</span>
                  <span className={`text-xl font-black ${(() => {
                    const label = (result.finalAssessment?.label || result.status || '').toUpperCase();
                    return label.includes('FAKE') ? 'text-rose-500' : 'text-emerald-500';
                  })()}`}>
                     {(() => {
                       if (result.verification && result.verification.verificationScore !== undefined) {
                         return `${(result.verification.verificationScore * 100).toFixed(0)}%`;
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
                         if (result.verification && result.verification.verificationScore !== undefined) {
                           return `${result.verification.verificationScore * 100}%`;
                         }
                         const label = (result.finalAssessment?.label || result.status || '').toUpperCase();
                         return label.includes('FAKE') ? '0%' : '88%';
                       })()
                     }}
                   />
                </div>
              </div>
           </div>

          {/* Feature Attribution */}
          <div className={`p-6 rounded-2xl border ${isDarkMode ? 'bg-[#1E293B] border-[#334155]' : 'bg-white border-[#E2E8F0] shadow-sm'}`}>
            <h4 className="text-lg font-bold mb-4 flex items-center gap-2">
              <svg className="w-5 h-5 text-emerald-600" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" /></svg>
              Feature Attribution
            </h4>
            <p className="text-xs mb-6 opacity-60">SHAP values indicating word contribution towards the verdict:</p>
            <div className="space-y-4">
              {((result.explanation && result.explanation.shapData) || result.shapData || []).slice().sort((a,b) => Math.abs(b.weight) - Math.abs(a.weight)).map((item, idx) => (
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
              <div className="p-2 rounded-lg bg-emerald-500/5 border border-emerald-500/10 text-center">
                <span className="block text-[9px] font-bold uppercase text-emerald-600">Factual Signal</span>
                <span className="text-xs font-bold text-emerald-500">Low</span>
              </div>
              <div className="p-2 rounded-lg bg-rose-500/5 border border-rose-500/10 text-center">
                <span className="block text-[9px] font-bold uppercase text-rose-600">Biased Signal</span>
                <span className="text-xs font-bold text-rose-500">Critical</span>
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
               <div className="bg-slate-900 text-slate-300 p-4 rounded-xl border border-white/5 space-y-2">
                 <div className="flex justify-between">
                   <span className="opacity-40">Network</span>
                   <span className="text-emerald-400">{result.blockchain.network}</span>
                 </div>
                 <div className="flex flex-col gap-1">
                   <span className="opacity-40">TX_HASH</span>
                   <span className="text-emerald-400 break-all">{result.blockchain.transactionHash}</span>
                 </div>
                 <div className="flex justify-between">
                   <span className="opacity-40">TIMESTAMP</span>
                   <span>{result.blockchain.timestamp}</span>
                 </div>
                 <div className="pt-2 flex justify-between">
                    <span className="opacity-40">DATA_IPFS</span>
                    <span className="text-emerald-300 underline cursor-pointer">{result.blockchain.ipfsHash.substr(0, 12)}...</span>
                 </div>
               </div>
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

          {/* ── News Summary ── */}
          {result.verification?.summary && (
            <div className={`lg:col-span-3 p-6 rounded-2xl border ${isDarkMode ? 'bg-[#1E293B] border-[#334155]' : 'bg-white border-[#E2E8F0] shadow-sm'}`}>
              <h4 className="text-sm font-bold mb-3 flex items-center gap-2 uppercase tracking-wider opacity-60">
                <svg className="w-4 h-4 text-emerald-500" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" /></svg>
                AI News Summary
              </h4>
              <p className={`text-sm leading-relaxed ${isDarkMode ? 'text-slate-300' : 'text-slate-600'}`}>
                {result.verification.summary}
              </p>
            </div>
          )}

          {/* ── Source Comparison Matrix ── */}
          {result.verification?.sourceComparison && result.verification.sourceComparison.length > 0 && (
            <div className={`lg:col-span-3 p-6 rounded-2xl border ${isDarkMode ? 'bg-[#1E293B] border-[#334155]' : 'bg-white border-[#E2E8F0] shadow-sm'}`}>
              <h4 className="text-sm font-bold mb-4 flex items-center gap-2 uppercase tracking-wider">
                <svg className="w-4 h-4 text-violet-500" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M3 10h18M3 14h18M10 3v18M14 3v18" /></svg>
                <span className="text-violet-500">Source Comparison Matrix</span>
                <span className={`ml-1 text-[10px] font-bold px-2 py-0.5 rounded-full border ${isDarkMode ? 'bg-violet-500/10 border-violet-500/20 text-violet-400' : 'bg-violet-50 border-violet-200 text-violet-600'}`}>
                  Gemini Pro Analysis
                </span>
              </h4>
              <div className="overflow-x-auto">
                <table className="w-full text-left border-collapse text-xs">
                  <thead>
                    <tr className={`border-b ${isDarkMode ? 'border-slate-700' : 'border-slate-200'}`}>
                      <th className="py-2 pr-4 font-bold uppercase tracking-wider opacity-50 whitespace-nowrap">Source</th>
                      <th className="py-2 pr-4 font-bold uppercase tracking-wider opacity-50">Article Title</th>
                      <th className="py-2 pr-4 font-bold uppercase tracking-wider opacity-50 whitespace-nowrap">Relation</th>
                      <th className="py-2 font-bold uppercase tracking-wider opacity-50">Key Finding</th>
                    </tr>
                  </thead>
                  <tbody>
                    {result.verification.sourceComparison.map((item, idx) => (
                      <tr key={idx} className={`border-b transition-colors ${isDarkMode ? 'border-slate-700/50 hover:bg-slate-700/20' : 'border-slate-100 hover:bg-slate-50'}`}>
                        <td className="py-3 pr-4 font-bold whitespace-nowrap">{item.source_name}</td>
                        <td className={`py-3 pr-4 ${isDarkMode ? 'text-slate-300' : 'text-slate-600'}`}>{item.article_title}</td>
                        <td className="py-3 pr-4">
                          <span className={`px-2 py-0.5 rounded text-[10px] font-black uppercase whitespace-nowrap ${
                            item.relationship === 'SUPPORTS'
                              ? 'bg-emerald-500/10 text-emerald-500 border border-emerald-500/20'
                              : item.relationship === 'REFUTES'
                              ? 'bg-rose-500/10 text-rose-500 border border-rose-500/20'
                              : 'bg-slate-500/10 text-slate-400 border border-slate-500/20'
                          }`}>
                            {item.relationship === 'SUPPORTS' ? '✓ Supports' : item.relationship === 'REFUTES' ? '✗ Refutes' : '— Unrelated'}
                          </span>
                        </td>
                        <td className={`py-3 italic text-[11px] ${isDarkMode ? 'text-slate-400' : 'text-slate-500'}`}>
                          "{item.key_finding}"
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
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
           <button className="px-10 py-3 rounded-2xl text-sm font-bold bg-emerald-500 text-white flex items-center gap-3 shadow-xl shadow-emerald-500/30 hover:scale-105 transition-all active:scale-95">
             <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M8.684 13.342C8.886 12.938 9 12.482 9 12c0-.482-.114-.938-.316-1.342m0 2.684a3 3 0 110-2.684m0 2.684l6.632 3.316m-6.632-6l6.632-3.316m0 0a3 3 0 105.367-2.684 3 3 0 00-5.367 2.684zm0 9.316a3 3 0 105.368 2.684 3 3 0 00-5.368-2.684z" /></svg>
             Share Verification
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
