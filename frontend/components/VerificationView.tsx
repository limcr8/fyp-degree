
import React, { useState, useEffect } from 'react';
import { VerificationResult, VerificationStatus } from '../types';
import { verifyNewsContent } from '../services/apiService';

interface VerificationViewProps {
  isDarkMode: boolean;
}

const VerificationView: React.FC<VerificationViewProps> = ({ isDarkMode }) => {
  const [inputText, setInputText] = useState('');
  const [isVerifying, setIsVerifying] = useState(false);
  const [result, setResult] = useState<VerificationResult | null>(null);

  const sampleData: VerificationResult = {
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
    sources: [
      { name: 'NASA Official', confirmed: false },
      { name: 'AP News', confirmed: false },
      { name: 'Space.com', confirmed: false },
      { name: 'Nature', confirmed: false }
    ],
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
      const apiResult = await verifyNewsContent(inputText);

      setResult(apiResult);
    } catch (err) {
      alert("Verification failed. Check console for details.");
    } finally {
      setIsVerifying(false);
    }
  };

  const getStatusColor = (status: VerificationStatus) => {
    switch (status) {
      case VerificationStatus.REAL: return 'text-emerald-500';
      case VerificationStatus.FAKE: return 'text-rose-500';
      default: return 'text-amber-500';
    }
  };

  const getStatusBg = (status: VerificationStatus) => {
    switch (status) {
      case VerificationStatus.REAL: return 'bg-emerald-500/10 border-emerald-500/20';
      case VerificationStatus.FAKE: return 'bg-rose-500/10 border-rose-500/20';
      default: return 'bg-amber-500/10 border-amber-500/20';
    }
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
            onChange={(e) => setInputText(e.target.value)}
            className={`w-full h-40 p-4 rounded-xl border focus:ring-2 focus:ring-emerald-500 outline-none transition-all ${isDarkMode ? 'bg-[#0F172A] border-[#334155] text-white' : 'bg-[#F8FAFC] border-[#E2E8F0] text-slate-800'}`}
            placeholder="Paste news text or article link here..."
          />
          {inputText && (
            <button 
              onClick={() => { setInputText(''); setResult(null); }}
              className="absolute top-4 right-4 text-slate-400 hover:text-slate-600"
            >
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12" /></svg>
            </button>
          )}
        </div>

        <div className="flex flex-col sm:flex-row gap-4 items-center justify-between">
           <div className="flex items-center gap-2">
              <span className="text-sm font-medium">Linguistic Engine:</span>
              <span className="px-2 py-1 bg-emerald-500/10 text-emerald-500 text-[10px] font-bold rounded uppercase">FastAPI Backend</span>
           </div>
           <div className="flex gap-4 w-full sm:w-auto">
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
           </div>
        </div>
      </section>

      {/* Results Section */}
      {result && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 animate-slide-up">
          {/* Main Verdict */}
          <div className={`lg:col-span-2 p-8 rounded-2xl border ${getStatusBg(result.status)} flex flex-col items-center justify-center text-center`}>
            <div className={`w-20 h-20 rounded-full mb-4 flex items-center justify-center ${getStatusColor(result.status)} bg-white shadow-xl`}>
               {result.status === VerificationStatus.REAL ? (
                 <svg className="w-12 h-12" fill="currentColor" viewBox="0 0 20 20"><path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" /></svg>
               ) : result.status === VerificationStatus.FAKE ? (
                 <svg className="w-12 h-12" fill="currentColor" viewBox="0 0 20 20"><path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clipRule="evenodd" /></svg>
               ) : (
                 <svg className="w-12 h-12" fill="currentColor" viewBox="0 0 20 20"><path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z" clipRule="evenodd" /></svg>
               )}
            </div>
            <h3 className={`text-4xl font-black uppercase tracking-tight mb-2 ${getStatusColor(result.status)}`}>
               VERDICT: {result.status}
            </h3>
            <div className="flex items-center gap-6 mt-4">
              <div className="text-center">
                <span className="block text-[10px] font-bold uppercase text-slate-400">Confidence</span>
                <span className="text-2xl font-black">{(result.confidence * 100).toFixed(1)}%</span>
              </div>
              <div className="h-10 w-px bg-slate-300"></div>
              <div className="text-center">
                <span className="block text-[10px] font-bold uppercase text-slate-400">Analysis Mode</span>
                <span className={`text-2xl font-black uppercase text-emerald-600`}>DEEP SCAN</span>
              </div>
            </div>
            <p className={`mt-6 text-lg max-w-xl leading-relaxed ${isDarkMode ? 'text-slate-200' : 'text-slate-700'}`}>
              {result.explanation}
            </p>
          </div>

          {/* SHAP Explanation */}
          <div className={`p-6 rounded-2xl border ${isDarkMode ? 'bg-[#1E293B] border-[#334155]' : 'bg-white border-[#E2E8F0] shadow-sm'}`}>
            <h4 className="text-lg font-bold mb-4 flex items-center gap-2">
              <svg className="w-5 h-5 text-emerald-600" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" /></svg>
              Feature Attribution
            </h4>
            <p className="text-xs mb-6 opacity-60">SHAP values indicating word contribution towards the verdict:</p>
            <div className="space-y-4">
              {result.shapData.sort((a,b) => Math.abs(b.weight) - Math.abs(a.weight)).map((item, idx) => (
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

          {/* Source Verification */}
          <div className={`p-6 rounded-2xl border ${isDarkMode ? 'bg-[#1E293B] border-[#334155]' : 'bg-white border-[#E2E8F0] shadow-sm'}`}>
            <h4 className="text-lg font-bold mb-4 flex items-center gap-2">
               <svg className="w-5 h-5 text-emerald-600" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19 20H5a2 2 0 01-2-2V6a2 2 0 012-2h10l4 4v10a2 2 0 01-2 2z" /><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M14 2v6h6" /><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M16 13H8" /><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M16 17H8" /><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M10 9H8" /></svg>
               Authority Matching
            </h4>
            <div className="space-y-2">
              {result.sources.map((source, idx) => (
                <div key={idx} className={`flex items-center justify-between p-3 rounded-xl ${isDarkMode ? 'bg-[#0F172A]' : 'bg-[#F8FAFC]'}`}>
                  <span className="font-bold text-xs">{source.name}</span>
                  {source.confirmed ? (
                    <span className="text-emerald-500 text-[10px] font-black bg-emerald-500/10 px-2 py-1 rounded-full border border-emerald-500/20">VALIDATED</span>
                  ) : (
                    <span className="text-rose-400 text-[10px] font-black bg-rose-500/10 px-2 py-1 rounded-full border border-rose-500/20 uppercase tracking-tighter">No Mention</span>
                  )}
                </div>
              ))}
            </div>
            <div className="mt-6 pt-6 border-t border-slate-200/20">
               <div className="flex justify-between items-end mb-2">
                 <span className="text-xs font-bold uppercase opacity-50">Grounding Score</span>
                 <span className={`text-xl font-black ${result.status === 'FAKE' ? 'text-rose-500' : 'text-emerald-500'}`}>
                    {result.status === 'FAKE' ? '0%' : '88%'}
                 </span>
               </div>
               <div className={`w-full h-2 rounded-full ${isDarkMode ? 'bg-[#0F172A]' : 'bg-slate-100'} overflow-hidden`}>
                  <div className={`h-full ${result.status === 'FAKE' ? 'bg-rose-500' : 'bg-emerald-500'}`} style={{ width: result.status === 'FAKE' ? '0%' : '88%' }} />
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
              <button className="py-2.5 rounded-xl bg-emerald-500 text-white font-bold text-xs hover:bg-emerald-600 transition-all shadow-md active:translate-y-0.5">
                Download Signed Report
              </button>
            </div>
          </div>
        </div>
      )}

      {result && (
        <div className="flex justify-center gap-4 py-12">
           <button className={`px-8 py-3 rounded-2xl text-sm font-bold flex items-center gap-3 transition-all ${isDarkMode ? 'bg-[#334155] hover:bg-[#475569] text-slate-300' : 'bg-white border-2 border-slate-100 hover:border-emerald-100 text-slate-500 shadow-sm'}`}>
             <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" /></svg>
             Manual Dispute
           </button>
           <button className="px-10 py-3 rounded-2xl text-sm font-bold bg-emerald-500 text-white flex items-center gap-3 shadow-xl shadow-emerald-500/30 hover:scale-105 transition-all active:scale-95">
             <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M8.684 13.342C8.886 12.938 9 12.482 9 12c0-.482-.114-.938-.316-1.342m0 2.684a3 3 0 110-2.684m0 2.684l6.632 3.316m-6.632-6l6.632-3.316m0 0a3 3 0 105.367-2.684 3 3 0 00-5.367 2.684zm0 9.316a3 3 0 105.368 2.684 3 3 0 00-5.368-2.684z" /></svg>
             Share Verification
           </button>
        </div>
      )}
    </div>
  );
};

export default VerificationView;
