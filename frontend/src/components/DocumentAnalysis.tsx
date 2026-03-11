import { useState } from "react";
import { FileText, DollarSign, Clock, CreditCard, Play, Square, Send, CheckCircle, Loader2, Scan } from "lucide-react";
import type { ScreenAnalysisStatus, ExtractedTerms } from "../types";

type ScanPhase = "ready" | "scanning" | "review";

interface DocumentAnalysisProps {
  isSharing: boolean;
  status: ScreenAnalysisStatus;
  terms?: ExtractedTerms;
  isShared: boolean;
  frameCount: number;
  onStartScan: () => void;
  onStopScan: () => void;
  onShare: () => void;
}

export default function DocumentAnalysis({
  isSharing,
  status,
  terms,
  isShared,
  frameCount,
  onStartScan,
  onStopScan,
  onShare,
}: DocumentAnalysisProps) {
  const [phase, setPhase] = useState<ScanPhase>("ready");

  if (!isSharing && !isShared) return null;

  const hasTerms = terms && Object.values(terms).some(v => v);
  const isAnalyzing = status === "analyzing";
  
  const termItems = hasTerms ? [
    { icon: DollarSign, label: "Price", value: terms?.price },
    { icon: CreditCard, label: "Payment", value: terms?.payment_terms },
    { icon: Clock, label: "Timeline", value: terms?.timeline },
    { icon: FileText, label: "Scope", value: terms?.scope },
  ].filter(t => t.value) : [];

  const handleStartScan = () => {
    setPhase("scanning");
    onStartScan();
  };

  const handleStopScan = () => {
    setPhase("review");
    onStopScan();
  };

  return (
    <div className="fixed left-4 top-16 z-40 animate-fade-in-up">
      <div className="flex flex-col gap-3 rounded-xl border border-indigo-400/20 bg-[#151C28] px-4 py-4 shadow-xl w-72">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Scan size={16} className="text-indigo-400" />
            <span className="text-sm font-semibold text-white">
              Document Scanner
            </span>
          </div>
          {isShared && (
            <span className="flex items-center gap-1 text-[10px] text-emerald-400 bg-emerald-400/10 px-2 py-0.5 rounded-full">
              <CheckCircle size={10} />
              Shared
            </span>
          )}
        </div>

        {/* Phase: Ready */}
        {phase === "ready" && !hasTerms && (
          <>
            <p className="text-xs text-slate-400 leading-relaxed">
              Click <strong>Start Analysis</strong> then scroll through your document. 
              The AI agent will extract all contract terms automatically.
            </p>
            <button
              onClick={handleStartScan}
              className="flex items-center justify-center gap-2 rounded-lg bg-indigo-500 px-4 py-2.5 text-sm font-medium text-white transition-colors hover:bg-indigo-600"
            >
              <Play size={14} />
              Start Analysis
            </button>
          </>
        )}

        {/* Phase: Scanning */}
        {phase === "scanning" && (
          <>
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <div className="h-2 w-2 rounded-full bg-red-500 animate-pulse" />
                <span className="text-xs text-red-400 font-medium">SCANNING</span>
              </div>
              <span className="text-xs text-slate-500">
                {frameCount} frame{frameCount !== 1 ? "s" : ""} captured
              </span>
            </div>
            
            <p className="text-xs text-slate-400">
              Scroll through your document now. The agent is extracting terms from each view.
            </p>

            {isAnalyzing && (
              <div className="flex items-center gap-2 text-xs text-purple-400">
                <Loader2 size={12} className="animate-spin" />
                Analyzing current view...
              </div>
            )}

            {/* Live extracted terms */}
            {termItems.length > 0 && (
              <div className="flex flex-col gap-1 bg-black/20 rounded-lg p-2 text-[11px]">
                {termItems.slice(0, 3).map(({ label, value }) => (
                  <div key={label} className="flex gap-1">
                    <span className="text-slate-500">{label}:</span>
                    <span className="text-slate-300 truncate">{value}</span>
                  </div>
                ))}
                {termItems.length > 3 && (
                  <span className="text-slate-500">+{termItems.length - 3} more...</span>
                )}
              </div>
            )}

            <button
              onClick={handleStopScan}
              className="flex items-center justify-center gap-2 rounded-lg bg-amber-500/20 border border-amber-500/30 px-4 py-2 text-sm font-medium text-amber-400 transition-colors hover:bg-amber-500/30"
            >
              <Square size={14} />
              Done Scanning
            </button>
          </>
        )}

        {/* Phase: Review (or has terms from previous scan) */}
        {(phase === "review" || (hasTerms && phase === "ready")) && (
          <>
            {/* Extracted terms */}
            {termItems.length > 0 && (
              <div className="flex flex-col gap-2">
                <div className="text-[10px] text-slate-500 uppercase tracking-wide">
                  Extracted Contract Terms
                </div>
                {termItems.map(({ icon: TermIcon, label, value }) => (
                  <div key={label} className="flex items-start gap-2 text-xs">
                    <TermIcon size={12} className="text-indigo-400/70 mt-0.5 shrink-0" />
                    <span className="text-slate-500 shrink-0 w-16">{label}:</span>
                    <span className="text-slate-200 leading-relaxed">{value}</span>
                  </div>
                ))}
              </div>
            )}

            {/* Action buttons */}
            <div className="flex flex-col gap-2 pt-2 border-t border-white/10">
              {!isShared && (
                <>
                  <button
                    onClick={onShare}
                    className="flex items-center justify-center gap-2 rounded-lg bg-emerald-500 px-4 py-2.5 text-sm font-medium text-white transition-colors hover:bg-emerald-600"
                  >
                    <Send size={14} />
                    Share with Counterpart
                  </button>
                  <p className="text-[10px] text-slate-500 text-center">
                    Counterpart will know these terms for the negotiation
                  </p>
                </>
              )}
              
              <button
                onClick={handleStartScan}
                className="flex items-center justify-center gap-1.5 rounded-lg bg-white/5 px-3 py-1.5 text-xs text-slate-400 transition-colors hover:bg-white/10"
              >
                <Scan size={12} />
                Scan Again
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
