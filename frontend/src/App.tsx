import { useState } from "react";
import {
  LayoutDashboard,
  Search,
  FileText,
  GitCompare,
  Download,
  Plus,
  Send,
  CheckCircle2,
  UploadCloud,
  Loader2,
} from "lucide-react";

import { PDFViewer } from "./components/PDFViewer";
import { CitationPanel } from "./components/CitationPanel";
import { AnswerViewer } from "./components/AnswerViewer";
import { DocumentNavigator } from "./components/DocumentNavigator";
import type { CitationData } from "./components/CitationCard";

export default function App() {
  const [activeTab, setActiveTab] = useState<string>("research");

  // State for Document Viewer inside Research workspace
  const [currentDocId] = useState<string>("doc-apple-q2-2025");
  const [currentPage, setCurrentPage] = useState<number>(52);
  const [totalPages] = useState<number>(97);
  const [activeCitationIdx, setActiveCitationIdx] = useState<number | undefined>(undefined);

  // Math-verified Mock Citations
  const citations: CitationData[] = [
    {
      chunk_id: "chunk_1",
      document_id: "doc-apple-q2-2025",
      page: 52,
      bbox: { x1: 150, y1: 220, x2: 850, y2: 320 },
      section: "MD&A - Inventory & Revenue Details",
      ticker: "AAPL",
      period: "Q2 2025",
      confidence: { similarity_score: 0.965, reranker_score: 0.941, verification_status: "verified" },
    },
    {
      chunk_id: "chunk_2",
      document_id: "doc-apple-q2-2025",
      page: 61,
      bbox: { x1: 200, y1: 450, x2: 800, y2: 550 },
      section: "Risk Factors - Raw Materials Pricing",
      ticker: "AAPL",
      period: "Q2 2025",
      confidence: { similarity_score: 0.912, reranker_score: 0.887, verification_status: "verified" },
    },
    {
      chunk_id: "chunk_3",
      document_id: "doc-apple-q2-2025",
      page: 72,
      bbox: { x1: 100, y1: 150, x2: 900, y2: 250 },
      section: "Financial Statements - Notes to FS",
      ticker: "AAPL",
      period: "Q2 2025",
      confidence: { similarity_score: 0.952, reranker_score: 0.923, verification_status: "verified" },
    },
  ];

  // Map box overlays on current page
  const pageBboxes = citations
    .filter((c) => c.page === currentPage)
    .map((c) => ({
      id: c.chunk_id,
      bbox: c.bbox,
      label: `${c.ticker} Cit. (${c.confidence.verification_status})`,
    }));

  const activeBbox = activeCitationIdx !== undefined ? citations[activeCitationIdx].bbox : undefined;

  const handleCitationSelect = (index: number, citation: CitationData) => {
    setActiveCitationIdx(index);
    setCurrentPage(citation.page);
  };

  // Upload list
  const recentUploads = [
    { name: "Apple_10-Q_Q2_2025.pdf", date: "May 20, 2025", size: "15.6 MB" },
    { name: "Tesla_10-K_2024.pdf", date: "May 18, 2025", size: "8.1 MB" },
    { name: "Microsoft_10-Q_Q1_2025.pdf", date: "May 17, 2025", size: "12.3 MB" },
  ];

  return (
    <div className="flex h-screen bg-slate-50 text-slate-800 font-sans overflow-hidden">
      {/* Sidebar Navigation */}
      <aside className="w-64 bg-white border-r border-slate-200 flex flex-col justify-between">
        <div>
          {/* Logo */}
          <div className="flex items-center gap-2 px-6 py-5 border-b border-slate-100 bg-slate-50/50">
            <div className="w-8 h-8 rounded-lg bg-blue-600 flex items-center justify-center text-white font-black text-lg shadow-md shadow-blue-500/20">
              F
            </div>
            <span className="text-base font-black tracking-wider text-slate-900">FinRAG</span>
            <span className="text-[9px] font-bold bg-blue-50 text-blue-600 px-1.5 py-0.5 rounded ml-auto">PRO</span>
          </div>

          {/* Nav Items */}
          <nav className="p-4 space-y-1">
            <button
              onClick={() => setActiveTab("dashboard")}
              className={`w-full flex items-center gap-3 px-4 py-2.5 rounded-lg text-sm font-semibold transition-all ${
                activeTab === "dashboard"
                  ? "bg-blue-50 text-blue-600 shadow-sm"
                  : "text-slate-600 hover:bg-slate-100 hover:text-slate-900"
              }`}
            >
              <LayoutDashboard size={18} />
              Dashboard
            </button>
            <button
              onClick={() => setActiveTab("research")}
              className={`w-full flex items-center gap-3 px-4 py-2.5 rounded-lg text-sm font-semibold transition-all ${
                activeTab === "research"
                  ? "bg-blue-50 text-blue-600 shadow-sm"
                  : "text-slate-600 hover:bg-slate-100 hover:text-slate-900"
              }`}
            >
              <Search size={18} />
              Research Workspace
            </button>
            <button
              onClick={() => setActiveTab("compare")}
              className={`w-full flex items-center gap-3 px-4 py-2.5 rounded-lg text-sm font-semibold transition-all ${
                activeTab === "compare"
                  ? "bg-blue-50 text-blue-600 shadow-sm"
                  : "text-slate-600 hover:bg-slate-100 hover:text-slate-900"
              }`}
            >
              <GitCompare size={18} />
              Compare Reports
            </button>
            <button
              onClick={() => setActiveTab("verification")}
              className={`w-full flex items-center gap-3 px-4 py-2.5 rounded-lg text-sm font-semibold transition-all ${
                activeTab === "verification"
                  ? "bg-blue-50 text-blue-600 shadow-sm"
                  : "text-slate-600 hover:bg-slate-100 hover:text-slate-900"
              }`}
            >
              <CheckCircle2 size={18} />
              Verification Panel
            </button>
            <button
              onClick={() => setActiveTab("pipeline")}
              className={`w-full flex items-center gap-3 px-4 py-2.5 rounded-lg text-sm font-semibold transition-all ${
                activeTab === "pipeline"
                  ? "bg-blue-50 text-blue-600 shadow-sm"
                  : "text-slate-600 hover:bg-slate-100 hover:text-slate-900"
              }`}
            >
              <UploadCloud size={18} />
              Upload & Pipeline
            </button>
          </nav>

          {/* Watchlist card */}
          <div className="px-4 mt-6">
            <div className="p-4 bg-slate-50 border border-slate-200/80 rounded-xl space-y-3">
              <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider">Portfolio Watchlist</span>
              <div className="space-y-2 text-xs font-semibold text-slate-700">
                <div className="flex justify-between">
                  <span>AAPL</span>
                  <span className="text-slate-900">$196.89</span>
                  <span className="text-green-600">+1.2%</span>
                </div>
                <div className="flex justify-between">
                  <span>TSLA</span>
                  <span className="text-slate-900">$178.59</span>
                  <span className="text-red-500">-2.4%</span>
                </div>
                <div className="flex justify-between">
                  <span>MSFT</span>
                  <span className="text-slate-900">$415.36</span>
                  <span className="text-green-600">+0.8%</span>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Profile Card & Info */}
        <div className="p-4 border-t border-slate-100 space-y-4 bg-slate-50/50">
          <div className="flex items-center gap-2 text-xs font-semibold text-slate-600">
            <span className="w-2 h-2 rounded-full bg-green-500" />
            <span>API Status: Healthy</span>
            <span className="ml-auto font-mono text-slate-400">GPT-4o</span>
          </div>

          <div className="flex items-center gap-3">
            <img
              src="https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=80&auto=format&fit=crop"
              alt="User"
              className="w-10 h-10 rounded-full border border-slate-200 shadow-sm"
            />
            <div className="flex flex-col">
              <span className="text-xs font-bold text-slate-900">Ram Kumar</span>
              <span className="text-[10px] text-slate-500 font-semibold">Enterprise Plan User</span>
            </div>
          </div>
        </div>
      </aside>

      {/* Main Content Area */}
      <main className="flex-1 flex flex-col overflow-hidden bg-slate-50">
        {/* Header bar */}
        <header className="h-16 bg-white border-b border-slate-200 flex items-center justify-between px-8">
          <h2 className="text-lg font-black text-slate-900 uppercase tracking-wide">
            {activeTab === "dashboard" && "Platform Operations"}
            {activeTab === "research" && "Financial Research Workspace"}
            {activeTab === "compare" && "Compare Filing Disclosures"}
            {activeTab === "verification" && "LLM Math & Fact Auditor"}
            {activeTab === "pipeline" && "Filing Pipeline Ingestion"}
          </h2>
          <div className="flex items-center gap-3">
            <span className="text-xs font-bold text-slate-400 bg-slate-100 px-3 py-1 rounded-full font-mono">
              FY 2025 Q3 Active
            </span>
          </div>
        </header>

        {/* Tab Contents */}
        <div className="flex-1 overflow-auto p-8">
          {/* TAB 1: DASHBOARD */}
          {activeTab === "dashboard" && (
            <div className="space-y-6">
              {/* Stat Cards */}
              <div className="grid grid-cols-1 md:grid-cols-5 gap-4">
                <div className="bg-white border border-slate-200 p-5 rounded-xl shadow-sm space-y-1">
                  <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider">Documents Ingested</span>
                  <div className="text-2xl font-black text-slate-900">128</div>
                  <span className="text-[10px] text-green-600 font-bold">+12 this week</span>
                </div>
                <div className="bg-white border border-slate-200 p-5 rounded-xl shadow-sm space-y-1">
                  <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider">Indexed Chunks</span>
                  <div className="text-2xl font-black text-slate-900">45,672</div>
                  <span className="text-[10px] text-green-600 font-bold">+4,329 this week</span>
                </div>
                <div className="bg-white border border-slate-200 p-5 rounded-xl shadow-sm space-y-1">
                  <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider">Vector Embeddings</span>
                  <div className="text-2xl font-black text-slate-900">45,672</div>
                  <span className="text-[10px] text-green-600 font-bold">+4,329 this week</span>
                </div>
                <div className="bg-white border border-slate-200 p-5 rounded-xl shadow-sm space-y-1">
                  <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider">QA Queries Run</span>
                  <div className="text-2xl font-black text-slate-900">342</div>
                  <span className="text-[10px] text-green-600 font-bold">+68 this week</span>
                </div>
                <div className="bg-white border border-slate-200 p-5 rounded-xl shadow-sm space-y-1">
                  <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider">Verified Answers</span>
                  <div className="text-2xl font-black text-green-600">98.6%</div>
                  <span className="text-[10px] text-green-600 font-bold">+2.1% this week</span>
                </div>
              </div>

              {/* Charts & Lists layout */}
              <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                {/* Recent Uploads */}
                <div className="bg-white border border-slate-200 p-6 rounded-xl shadow-sm flex flex-col gap-4">
                  <h4 className="text-xs font-bold text-slate-800 uppercase tracking-wider pb-2 border-b border-slate-100">
                    Recent Filing Uploads
                  </h4>
                  <div className="divide-y divide-slate-100 space-y-3">
                    {recentUploads.map((file, i) => (
                      <div key={i} className="flex items-center gap-3 pt-3 first:pt-0">
                        <div className="p-2 bg-blue-50 text-blue-600 rounded-lg">
                          <FileText size={18} />
                        </div>
                        <div className="flex flex-col">
                          <span className="text-xs font-bold text-slate-800 line-clamp-1">{file.name}</span>
                          <span className="text-[10px] text-slate-500 font-semibold">{file.date} • {file.size}</span>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Recent Inquiries */}
                <div className="bg-white border border-slate-200 p-6 rounded-xl shadow-sm flex flex-col gap-4">
                  <h4 className="text-xs font-bold text-slate-800 uppercase tracking-wider pb-2 border-b border-slate-100">
                    Recent Questions
                  </h4>
                  <ul className="space-y-3.5 text-xs font-bold text-slate-700">
                    <li className="flex items-start gap-2 hover:text-blue-600 cursor-pointer">
                      <span className="text-blue-500 font-mono">Q.</span> Compare Apple and Tesla inventory risks
                    </li>
                    <li className="flex items-start gap-2 hover:text-blue-600 cursor-pointer">
                      <span className="text-blue-500 font-mono">Q.</span> What drove Microsoft's cloud growth?
                    </li>
                    <li className="flex items-start gap-2 hover:text-blue-600 cursor-pointer">
                      <span className="text-blue-500 font-mono">Q.</span> Apple Q2 2025 earnings call summary
                    </li>
                  </ul>
                </div>

                {/* Research Activity SVG Bar Chart */}
                <div className="bg-white border border-slate-200 p-6 rounded-xl shadow-sm flex flex-col gap-4">
                  <h4 className="text-xs font-bold text-slate-800 uppercase tracking-wider pb-2 border-b border-slate-100">
                    Filing Activity (This Week)
                  </h4>
                  <div className="flex items-end justify-between h-44 pt-4 px-2">
                    {[35, 65, 45, 85, 55, 95, 75].map((val, i) => (
                      <div key={i} className="flex flex-col items-center gap-2 w-full">
                        <div
                          style={{ height: `${val}px` }}
                          className="w-4 rounded-t bg-blue-600/80 hover:bg-blue-600 transition-colors shadow-sm shadow-blue-500/10"
                        />
                        <span className="text-[9px] text-slate-400 font-bold font-mono">
                          {["M", "T", "W", "T", "F", "S", "S"][i]}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* TAB 2: RESEARCH WORKSPACE */}
          {activeTab === "research" && (
            <div className="flex gap-6 h-[calc(100vh-170px)]">
              {/* Workspace Left panel: Document scopes */}
              <div className="w-60 bg-white border border-slate-200 rounded-xl p-4 flex flex-col justify-between">
                <div className="space-y-4">
                  <div className="flex items-center justify-between pb-2 border-b border-slate-100">
                    <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider">Documents</span>
                    <button className="flex items-center gap-0.5 text-[10px] font-bold text-blue-600 hover:text-blue-700 bg-blue-50 px-1.5 py-0.5 rounded">
                      <Plus size={10} /> Add
                    </button>
                  </div>
                  <div className="space-y-1.5">
                    <div className="p-2 bg-blue-50 border border-blue-200/50 rounded-lg text-xs font-bold text-slate-800 flex items-center gap-2 cursor-pointer">
                      <FileText size={14} className="text-blue-500" />
                      AAPL 10-Q (Q2 2025)
                    </div>
                    <div className="p-2 hover:bg-slate-50 border border-transparent rounded-lg text-xs font-semibold text-slate-600 flex items-center gap-2 cursor-pointer">
                      <FileText size={14} className="text-slate-400" />
                      TSLA 10-K (2024)
                    </div>
                    <div className="p-2 hover:bg-slate-50 border border-transparent rounded-lg text-xs font-semibold text-slate-600 flex items-center gap-2 cursor-pointer">
                      <FileText size={14} className="text-slate-400" />
                      MSFT 10-Q (Q1 2025)
                    </div>
                  </div>
                </div>

                <div className="space-y-2 pt-4 border-t border-slate-100">
                  <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider">Section Filter</span>
                  <div className="space-y-1 text-xs font-bold text-slate-600">
                    <div className="flex justify-between p-1 hover:text-slate-800 cursor-pointer">
                      <span>All Sections</span>
                      <span className="font-mono text-slate-400">328</span>
                    </div>
                    <div className="flex justify-between p-1 text-blue-600 bg-blue-50 rounded">
                      <span>MD&A</span>
                      <span className="font-mono">86</span>
                    </div>
                    <div className="flex justify-between p-1 hover:text-slate-800 cursor-pointer">
                      <span>Risk Factors</span>
                      <span className="font-mono text-slate-400">62</span>
                    </div>
                    <div className="flex justify-between p-1 hover:text-slate-800 cursor-pointer">
                      <span>Notes to FS</span>
                      <span className="font-mono text-slate-400">71</span>
                    </div>
                  </div>
                </div>
              </div>

              {/* Workspace Middle panel: QA thread */}
              <div className="flex-1 flex flex-col justify-between bg-white border border-slate-200 rounded-xl overflow-hidden shadow-sm p-4">
                <div className="space-y-5 overflow-y-auto pr-1">
                  {/* User Question */}
                  <div className="flex gap-2">
                    <div className="w-6 h-6 rounded-full bg-slate-200 flex items-center justify-center text-[10px] font-bold text-slate-600 uppercase">
                      RK
                    </div>
                    <div className="flex-1 bg-slate-100 p-3.5 rounded-r-xl rounded-bl-xl">
                      <p className="text-slate-700 text-xs font-bold leading-relaxed">
                        Compare Apple's inventory risks with Tesla.
                      </p>
                    </div>
                  </div>

                  {/* AI Response with clickable annotations */}
                  <div className="flex gap-2">
                    <div className="w-6 h-6 rounded-full bg-blue-600 flex items-center justify-center text-white text-[10px] font-black uppercase">
                      AI
                    </div>
                    <div className="flex-1 space-y-4">
                      <AnswerViewer
                        answer={
                          "Apple's inventory risk is lower compared to Tesla. Apple maintains a high inventory turnover driven by strong demand and diversified product lines [1], while Tesla faces higher inventory risk due to production volatility and supply chain constraints [2].\n\nAdditionally, Apple is more exposed to raw material price volatility [3]."
                        }
                        citations={citations}
                        activeCitationIndex={activeCitationIdx}
                        onCitationClick={handleCitationSelect}
                      />
                    </div>
                  </div>
                </div>

                {/* QA Input Box */}
                <div className="mt-4 border-t border-slate-100 pt-3 flex gap-2">
                  <input
                    type="text"
                    defaultValue="Compare Apple's inventory risks with Tesla."
                    className="flex-1 px-4 py-2 bg-slate-50 border border-slate-200 rounded-xl text-xs text-slate-700 font-bold focus:outline-none focus:border-blue-500"
                  />
                  <button className="p-2.5 bg-blue-600 text-white rounded-xl hover:bg-blue-700 shadow-md shadow-blue-500/10">
                    <Send size={14} />
                  </button>
                </div>
              </div>

              {/* Workspace Right panel: Document coordinate overlays & Citation Panel stacked */}
              <div className="w-[500px] flex-shrink-0 flex flex-col gap-4">
                <div className="flex-1 min-h-0">
                  <PDFViewer
                    documentId={currentDocId}
                    currentPage={currentPage}
                    totalPages={totalPages}
                    activeBbox={activeBbox}
                    bboxes={pageBboxes}
                    onBboxClick={(chunkId) => {
                      const idx = citations.findIndex((c) => c.chunk_id === chunkId);
                      if (idx !== -1) {
                        setActiveCitationIdx(idx);
                      }
                    }}
                    onPageChange={setCurrentPage}
                  />
                </div>

                <DocumentNavigator
                  documentId={currentDocId}
                  currentPage={currentPage}
                  totalPages={totalPages}
                  ticker="AAPL"
                  period="Q2 2025"
                  year={2025}
                  onPageSelect={setCurrentPage}
                />

                {/* Staked citations list underneath */}
                <div className="h-[220px] flex-shrink-0 border border-slate-200 rounded-xl overflow-hidden shadow-sm flex flex-col">
                  <CitationPanel
                    citations={citations}
                    activeIndex={activeCitationIdx}
                    onCitationClick={(idx, citation) => handleCitationSelect(idx, citation)}
                  />
                </div>
              </div>
            </div>
          )}

          {/* TAB 3: COMPARE REPORTS */}
          {activeTab === "compare" && (
            <div className="space-y-6">
              {/* Inputs */}
              <div className="bg-white border border-slate-200 p-5 rounded-xl flex items-center justify-between flex-wrap gap-4 shadow-sm">
                <div className="flex items-center gap-4 flex-wrap">
                  <div className="flex flex-col gap-1">
                    <label className="text-[10px] font-bold text-slate-400 uppercase">Ticker</label>
                    <select className="px-3 py-1.5 bg-slate-50 border border-slate-200 rounded-lg text-xs font-bold text-slate-700 focus:outline-none focus:border-blue-500">
                      <option>Apple Inc. (AAPL)</option>
                      <option>Tesla Inc. (TSLA)</option>
                    </select>
                  </div>

                  <div className="flex flex-col gap-1">
                    <label className="text-[10px] font-bold text-slate-400 uppercase">Filing Period A</label>
                    <select className="px-3 py-1.5 bg-slate-50 border border-slate-200 rounded-lg text-xs font-bold text-slate-700 focus:outline-none focus:border-blue-500">
                      <option>Q1 2025 (10-Q)</option>
                      <option>Q2 2025 (10-Q)</option>
                    </select>
                  </div>

                  <div className="flex flex-col gap-1">
                    <label className="text-[10px] font-bold text-slate-400 uppercase">Filing Period B</label>
                    <select className="px-3 py-1.5 bg-slate-50 border border-slate-200 rounded-lg text-xs font-bold text-slate-700 focus:outline-none focus:border-blue-500">
                      <option>Q2 2025 (10-Q)</option>
                      <option>Q3 2025 (10-Q)</option>
                    </select>
                  </div>
                </div>

                <div className="flex gap-2">
                  <button className="px-5 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 text-xs font-bold shadow-md shadow-blue-500/10">
                    Compare periods
                  </button>
                  <button className="px-3.5 py-2 border border-slate-200 bg-white rounded-lg text-slate-600 hover:bg-slate-50 text-xs font-bold flex items-center gap-1.5">
                    <Download size={14} /> Export
                  </button>
                </div>
              </div>

              {/* Side-by-side comparison tables */}
              <div className="bg-white border border-slate-200 rounded-xl shadow-sm overflow-hidden flex flex-col">
                {/* Tab selections */}
                <div className="flex border-b border-slate-100 text-xs font-bold text-slate-500">
                  <span className="px-5 py-3 border-b-2 border-blue-600 text-blue-600 bg-blue-50/20 cursor-pointer">
                    Lexical Diff
                  </span>
                  <span className="px-5 py-3 hover:text-slate-800 cursor-pointer border-b-2 border-transparent">
                    Semantic Diff
                  </span>
                  <span className="px-5 py-3 hover:text-slate-800 cursor-pointer border-b-2 border-transparent">
                    Risk Shift Analysis
                  </span>
                </div>

                <div className="grid grid-cols-2 divide-x divide-slate-200 text-xs font-bold">
                  {/* Period A */}
                  <div className="p-6 bg-slate-50/50 flex flex-col gap-4">
                    <span className="text-[10px] text-slate-400 uppercase tracking-wider">Q1 2025 (10-Q)</span>
                    <div className="p-4 bg-white border border-slate-200 rounded-lg space-y-4 font-semibold text-slate-700">
                      <p className="bg-red-50 text-red-700 p-2.5 rounded border border-red-100">
                        - Inventory was $6.98 billion as of December 28, 2024, compared to $5.37 billion as of
                        December 30, 2023.
                      </p>
                      <p className="p-2.5 bg-slate-50 rounded">
                        We expect supply constraints to ease in the coming quarters.
                      </p>
                    </div>
                  </div>

                  {/* Period B */}
                  <div className="p-6 flex flex-col gap-4 bg-white">
                    <span className="text-[10px] text-slate-400 uppercase tracking-wider">Q2 2025 (10-Q)</span>
                    <div className="p-4 bg-slate-50 border border-slate-200 rounded-lg space-y-4 font-semibold text-slate-700">
                      <p className="bg-green-50 text-green-700 p-2.5 rounded border border-green-100">
                        + Inventory was $6.64 billion as of March 29, 2025, compared to $5.98 billion as of
                        March 30, 2024.
                      </p>
                      <p className="p-2.5 bg-yellow-50 text-yellow-800 rounded border border-yellow-100">
                        • We continue to experience supply chain constraints, particularly for key components and
                        materials.
                      </p>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* TAB 4: VERIFICATION PANEL */}
          {activeTab === "verification" && (
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
              {/* Left & Middle Column: Audited reports list */}
              <div className="lg:col-span-2 bg-white border border-slate-200 p-6 rounded-xl shadow-sm space-y-6">
                <div className="flex items-center justify-between pb-3 border-b border-slate-100">
                  <h4 className="text-sm font-bold text-slate-800 uppercase tracking-wide">
                    Calculation Auditor Summary
                  </h4>
                  <span className="px-2.5 py-1 bg-green-50 border border-green-200 text-green-700 rounded-full text-[10px] font-bold">
                    ✓ All checks passed
                  </span>
                </div>

                <div className="space-y-4">
                  <div className="flex items-center justify-between p-4 bg-slate-50 border border-slate-200/80 rounded-xl">
                    <div className="flex items-center gap-3">
                      <div className="w-8 h-8 rounded-full bg-green-50 border border-green-200 flex items-center justify-center text-green-700 font-bold text-xs">
                        ✓
                      </div>
                      <div className="flex flex-col">
                        <span className="text-xs font-bold text-slate-800">Mathematical Validation</span>
                        <span className="text-[10px] text-slate-400 font-semibold">Sandbox code execution matches text metrics.</span>
                      </div>
                    </div>
                    <span className="text-[10px] font-bold text-green-700 bg-green-50 px-2 py-0.5 rounded">PASS</span>
                  </div>

                  <div className="flex items-center justify-between p-4 bg-slate-50 border border-slate-200/80 rounded-xl">
                    <div className="flex items-center gap-3">
                      <div className="w-8 h-8 rounded-full bg-green-50 border border-green-200 flex items-center justify-center text-green-700 font-bold text-xs">
                        ✓
                      </div>
                      <div className="flex flex-col">
                        <span className="text-xs font-bold text-slate-800">Coordinate Citations Valid</span>
                        <span className="text-[10px] text-slate-400 font-semibold">All inline tags map exactly to document boundaries.</span>
                      </div>
                    </div>
                    <span className="text-[10px] font-bold text-green-700 bg-green-50 px-2 py-0.5 rounded">PASS</span>
                  </div>

                  <div className="flex items-center justify-between p-4 bg-slate-50 border border-slate-200/80 rounded-xl">
                    <div className="flex items-center gap-3">
                      <div className="w-8 h-8 rounded-full bg-green-50 border border-green-200 flex items-center justify-center text-green-700 font-bold text-xs">
                        ✓
                      </div>
                      <div className="flex flex-col">
                        <span className="text-xs font-bold text-slate-800">Hallucination Audit</span>
                        <span className="text-[10px] text-slate-400 font-semibold">Text claims align strictly with Qdrant payloads.</span>
                      </div>
                    </div>
                    <span className="text-[10px] font-bold text-green-700 bg-green-50 px-2 py-0.5 rounded">PASS</span>
                  </div>
                </div>
              </div>

              {/* Right Column: Radial Confidence Audit */}
              <div className="bg-white border border-slate-200 p-6 rounded-xl shadow-sm flex flex-col items-center justify-center gap-5 text-center">
                <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider">Overall Confidence</span>
                <div className="relative w-36 h-36 flex items-center justify-center">
                  <svg className="w-full h-full transform -rotate-90">
                    <circle cx="72" cy="72" r="60" stroke="#f1f5f9" strokeWidth="8" fill="transparent" />
                    <circle
                      cx="72"
                      cy="72"
                      r="60"
                      stroke="#2563eb"
                      strokeWidth="8"
                      fill="transparent"
                      strokeDasharray="377"
                      strokeDashoffset="12"
                    />
                  </svg>
                  <span className="absolute text-3xl font-black text-slate-900 font-mono">98%</span>
                </div>
                <p className="text-xs text-slate-500 font-semibold">
                  Synthesized response has successfully verified mathematical bounds and fact citation checks.
                </p>
              </div>
            </div>
          )}

          {/* TAB 5: PIPELINE */}
          {activeTab === "pipeline" && (
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
              {/* File Dropzone */}
              <div className="bg-white border-2 border-dashed border-slate-300 hover:border-blue-500 rounded-xl p-8 shadow-sm flex flex-col items-center justify-center text-center cursor-pointer min-h-[300px] transition-colors">
                <UploadCloud size={44} className="text-slate-400 mb-3" />
                <span className="text-xs font-bold text-slate-800">Drag & drop PDF files here</span>
                <p className="text-[10px] text-slate-400 font-semibold mt-1">or click to browse local files</p>
                <button className="mt-4 px-4 py-1.5 bg-slate-950 text-white rounded-lg text-xs font-bold hover:bg-slate-800">
                  Select Files
                </button>
              </div>

              {/* Processing statuses list */}
              <div className="lg:col-span-2 bg-white border border-slate-200 p-6 rounded-xl shadow-sm space-y-5">
                <h4 className="text-xs font-bold text-slate-800 uppercase tracking-wider pb-2 border-b border-slate-100">
                  Ingestion & Processing Pipeline
                </h4>
                <div className="space-y-3.5">
                  <div className="flex items-center justify-between text-xs font-bold">
                    <span className="text-slate-600">1. PDF Structural Parsing</span>
                    <span className="text-green-600">Complete ✓</span>
                  </div>
                  <div className="flex items-center justify-between text-xs font-bold">
                    <span className="text-slate-600">2. Layout Text & Tables Extraction</span>
                    <span className="text-green-600">Complete ✓</span>
                  </div>
                  <div className="flex items-center justify-between text-xs font-bold">
                    <span className="text-slate-600">3. Semantic Chunking Boundaries</span>
                    <span className="text-green-600">Complete ✓</span>
                  </div>
                  <div className="flex items-center justify-between text-xs font-bold">
                    <span className="text-slate-600">4. Dense Vector Generation</span>
                    <span className="text-blue-600 flex items-center gap-1">
                      <Loader2 size={12} className="animate-spin" /> Running
                    </span>
                  </div>
                  <div className="flex items-center justify-between text-xs font-bold text-slate-400">
                    <span>5. Qdrant Index Registration</span>
                    <span>Pending</span>
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>
      </main>
    </div>
  );
}
