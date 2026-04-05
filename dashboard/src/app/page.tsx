"use client";

import React, { useState, useMemo } from 'react';
import { motion } from 'framer-motion';
import { 
  ShieldAlert, 
  BrainCircuit,
  CheckCircle2, 
  FileSearch,
  AlertOctagon,
  ChevronRight,
  Users,
  Lightbulb
} from 'lucide-react';
import { 
  BarChart, 
  Bar, 
  XAxis, 
  YAxis, 
  CartesianGrid, 
  Tooltip, 
  ResponsiveContainer,
  Cell
} from 'recharts';

export default function Dashboard() {
  const [activeReport, setActiveReport] = useState<string | null>(null);
  const [rawAuditData, setRawAuditData] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  const monthOrder: Record<string, number> = {
    "January": 1, "February": 2, "March": 3, "April": 4, 
    "May": 5, "June": 6, "July": 7, "August": 8, 
    "September": 9, "October": 10, "November": 11, "December": 12
  };

  React.useEffect(() => {
    const fetchData = () => {
      fetch('/api/audit-results')
        .then(res => res.json())
        .then(data => {
          if (!data.error) setRawAuditData(data);
          setLoading(false);
        })
        .catch(err => {
          console.error(err);
          setLoading(false);
        });
    };

    fetchData(); // Initial load
    const intervalId = setInterval(fetchData, 10000); // Poll every 10s
    return () => clearInterval(intervalId);
  }, []);

  const processedData = useMemo(() => {
    if (!rawAuditData || rawAuditData.length === 0) return null;

    let validData = rawAuditData.filter(d => 
      d.status === "complete" && d.period !== "Unknown"
    );

    const seenPeriods = new Set<string>();
    validData = validData.filter(d => {
      if (seenPeriods.has(d.period)) return false;
      seenPeriods.add(d.period);
      return true;
    });

    validData.sort((a, b) => {
      const [mA, yA] = a.period.split(' ');
      const [mB, yB] = b.period.split(' ');
      if (yA !== yB) return parseInt(yA) - parseInt(yB);
      return monthOrder[mA] - monthOrder[mB];
    });

    const totalFiles = validData.length;
    const totalChecks = validData.reduce((acc, curr) => acc + curr.total_checks, 0);
    const passedChecks = validData.reduce((acc, curr) => acc + curr.checks_passed, 0);
    const totalRedFlags = validData.reduce((acc, curr) => acc + curr.red_flags_count, 0);
    const avgConfidence = validData.reduce((acc, curr) => acc + curr.confidence, 0) / (totalFiles || 1);

    const chartData = validData.map(d => ({
      name: d.period.replace(' 202', ' \'2'),
      flags: d.red_flags_count,
      passed: d.checks_passed,
      failed: d.total_checks - d.checks_passed,
      tooltipLabel: `${d.period} - Confidence: ${(d.confidence*100).toFixed(0)}%`
    }));

    return {
      validData, chartData,
      kpis: { totalFiles, totalChecks, passedChecks, totalRedFlags, avgConfidence }
    };
  }, [rawAuditData, monthOrder]);

  if (loading || !processedData) {
    return (
      <div className="min-h-screen bg-[#0A0A0B] flex items-center justify-center text-slate-400">
        <div className="flex flex-col items-center gap-4">
          <BrainCircuit className="w-12 h-12 animate-pulse text-indigo-500/50" />
          <p className="text-sm uppercase tracking-widest">Loading Live Audit Data...</p>
        </div>
      </div>
    );
  }

  const { validData, chartData, kpis } = processedData;

  return (
    <div className="min-h-screen bg-[#0A0A0B] text-slate-200 font-sans selection:bg-indigo-500/30">
      
      <div className="fixed inset-0 overflow-hidden pointer-events-none">
        <div className="absolute top-[-20%] left-[-10%] w-[50%] h-[50%] rounded-full bg-indigo-900/10 blur-[120px]" />
        <div className="absolute bottom-[-20%] right-[-10%] w-[50%] h-[50%] rounded-full bg-rose-900/10 blur-[120px]" />
      </div>

      <div className="relative max-w-7xl mx-auto px-6 py-12">
        
        <header className="mb-12 border-b border-white/10 pb-8 flex justify-between items-end">
          <div>
            <div className="flex items-center gap-3 mb-2">
              <div className="p-2 bg-indigo-500/10 border border-indigo-500/20 rounded-lg">
                <BrainCircuit className="w-6 h-6 text-indigo-400" />
              </div>
              <h1 className="text-3xl font-light tracking-tight text-white">
                HOA Audit <span className="font-semibold text-transparent bg-clip-text bg-gradient-to-r from-indigo-400 to-cyan-400">Swarm</span>
              </h1>
            </div>
            <p className="text-slate-400 pl-1">Deterministic Financial Verification Engine</p>
          </div>
          <div className="text-right">
            <div className="flex items-center gap-4 mb-3">
              <a href="/data-warehouse" className="px-4 py-2 text-sm font-medium bg-white/5 hover:bg-white/10 text-cyan-400 border border-cyan-500/30 rounded-lg transition-colors flex items-center gap-2">
                <FileSearch className="w-4 h-4" />
                Data Warehouse
              </a>
            </div>
            <div className="flex items-center gap-2 justify-end">
              <span className="relative flex h-3 w-3">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
                <span className="relative inline-flex rounded-full h-3 w-3 bg-emerald-500"></span>
              </span>
              <span className="text-emerald-400 font-medium text-sm">System Online</span>
            </div>
          </div>
        </header>

        <div className="grid grid-cols-1 md:grid-cols-4 gap-6 mb-12">
          
          <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.1 }}
            className="bg-white/[0.02] border border-white/5 rounded-2xl p-6 backdrop-blur-xl">
            <div className="flex items-center gap-3 text-slate-400 mb-4">
              <FileSearch className="w-5 h-5 text-cyan-400" />
              <h3 className="font-medium text-sm uppercase tracking-wider">Periods Audited</h3>
            </div>
            <div className="text-4xl font-light text-white">{kpis.totalFiles} <span className="text-lg text-slate-500">months</span></div>
          </motion.div>

          <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.2 }}
            className="bg-white/[0.02] border border-white/5 rounded-2xl p-6 backdrop-blur-xl">
            <div className="flex items-center gap-3 text-slate-400 mb-4">
              <ShieldAlert className="w-5 h-5 text-rose-400" />
              <h3 className="font-medium text-sm uppercase tracking-wider">Critical Red Flags</h3>
            </div>
            <div className="text-4xl font-semibold text-rose-400">{kpis.totalRedFlags}</div>
          </motion.div>

          <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.3 }}
            className="bg-white/[0.02] border border-white/5 rounded-2xl p-6 backdrop-blur-xl">
            <div className="flex items-center gap-3 text-slate-400 mb-4">
              <CheckCircle2 className="w-5 h-5 text-emerald-400" />
              <h3 className="font-medium text-sm uppercase tracking-wider">Math Validated</h3>
            </div>
            <div className="text-4xl font-light text-white">{(kpis.passedChecks / kpis.totalChecks * 100).toFixed(1)}<span className="text-lg text-slate-500">%</span></div>
          </motion.div>

          <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.4 }}
            className="bg-white/[0.02] border border-white/5 rounded-2xl p-6 backdrop-blur-xl">
            <div className="flex items-center gap-3 text-slate-400 mb-4">
              <BrainCircuit className="w-5 h-5 text-indigo-400" />
              <h3 className="font-medium text-sm uppercase tracking-wider">AI Confidence</h3>
            </div>
            <div className="text-4xl font-light text-white">{(kpis.avgConfidence * 100).toFixed(0)}<span className="text-lg text-slate-500">%</span></div>
          </motion.div>

        </div>

        {/* Architecture Visualizer */}
        <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.45 }}
          className="bg-white/[0.02] border border-white/5 rounded-3xl p-8 backdrop-blur-xl mb-12">
          <div className="mb-8">
            <h2 className="text-xl font-medium text-white">LangGraph Pipeline Architecture</h2>
            <p className="text-sm text-slate-400">The "Sandwich" Pattern: LLMs handle unstructured routing, while python handles deterministic math.</p>
          </div>
          
          <div className="flex flex-col md:flex-row items-center justify-between gap-4 w-full relative">
            <div className="absolute top-1/2 left-0 w-full h-0.5 bg-gradient-to-r from-transparent via-white/10 to-transparent -z-10 hidden md:block"></div>
            
            <div className="flex flex-col items-center gap-3 bg-[#0A0A0B] p-4 rounded-xl border border-white/10 w-full md:w-48 text-center shrink-0 z-10 shadow-xl">
              <FileSearch className="w-8 h-8 text-slate-400" />
              <div>
                <div className="font-medium text-white text-sm">PDF Ingestion</div>
                <div className="text-xs text-slate-500">LlamaParse</div>
              </div>
            </div>

            <ChevronRight className="w-6 h-6 text-white/20 shrink-0 hidden md:block" />

            <div className="flex flex-col items-center gap-3 bg-indigo-500/10 p-4 rounded-xl border border-indigo-500/30 w-full md:w-48 text-center shrink-0 z-10 shadow-[0_0_30px_rgba(99,102,241,0.1)]">
              <BrainCircuit className="w-8 h-8 text-indigo-400" />
              <div>
                <div className="font-medium text-indigo-300 text-sm">Triage Router</div>
                <div className="text-xs text-indigo-500/70">Claude 3.5 Sonnet</div>
              </div>
            </div>

            <ChevronRight className="w-6 h-6 text-white/20 shrink-0 hidden md:block" />

            <div className="flex flex-col gap-3 w-full md:w-56 shrink-0 z-10">
              <div className="flex items-center gap-3 bg-[#0A0A0B] p-3 rounded-lg border border-white/10">
                <BrainCircuit className="w-4 h-4 text-indigo-400" />
                <span className="text-xs text-slate-300 font-medium">1. Extract Invoices (LLM)</span>
              </div>
              <div className="flex items-center gap-3 bg-[#0A0A0B] p-3 rounded-lg border border-white/10">
                <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                <span className="text-xs text-slate-300 font-medium">2. Parse Bank (Regex)</span>
              </div>
              <div className="flex items-center gap-3 bg-[#0A0A0B] p-3 rounded-lg border border-white/10">
                <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                <span className="text-xs text-slate-300 font-medium">3. Parse Ledgers (Regex)</span>
              </div>
            </div>

            <ChevronRight className="w-6 h-6 text-white/20 shrink-0 hidden md:block" />

            <div className="flex flex-col items-center gap-3 bg-emerald-500/10 p-4 rounded-xl border border-emerald-500/30 w-full md:w-48 text-center shrink-0 z-10 shadow-[0_0_30px_rgba(16,185,129,0.1)]">
              <ShieldAlert className="w-8 h-8 text-emerald-400" />
              <div>
                <div className="font-medium text-emerald-300 text-sm">Deterministic Audit</div>
                <div className="text-xs text-emerald-500/70">Pure Python Math</div>
              </div>
            </div>
            
          </div>
        </motion.div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          
          <motion.div initial={{ opacity: 0, scale: 0.95 }} animate={{ opacity: 1, scale: 1 }} transition={{ delay: 0.5 }}
            className="lg:col-span-2 bg-gradient-to-b from-white/[0.03] to-transparent border border-white/10 rounded-3xl p-8 backdrop-blur-md">
            <div className="mb-8">
              <h2 className="text-xl font-medium text-white">Red Flag Trendline</h2>
              <p className="text-sm text-slate-400">Total unapproved checks or severe anomalies detected per month</p>
            </div>
            <div className="h-80 w-full">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={chartData} margin={{ top: 0, right: 0, left: -20, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#ffffff10" vertical={false} />
                  <XAxis dataKey="name" stroke="#ffffff40" fontSize={12} tickLine={false} axisLine={false} dy={10} />
                  <YAxis stroke="#ffffff40" fontSize={12} tickLine={false} axisLine={false} />
                  <Tooltip 
                    cursor={{fill: '#ffffff05'}}
                    contentStyle={{ backgroundColor: '#1e1e24', border: '1px solid rgba(255,255,255,0.1)', borderRadius: '12px', color: '#fff' }}
                  />
                  <Bar dataKey="flags" name="Red Flags" radius={[6, 6, 0, 0]}>
                    {chartData.map((entry: any, index: number) => (
                      <Cell key={`cell-${index}`} fill={entry.flags > 0 ? '#fb7185' : '#34d399'} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          </motion.div>

          <motion.div initial={{ opacity: 0, x: 20 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: 0.6 }}
            className="bg-white/[0.02] border border-white/10 rounded-3xl p-6 backdrop-blur-md flex flex-col h-full">
            <h2 className="text-xl font-medium text-white mb-6">Audit Reports</h2>
            <div className="flex-1 overflow-y-auto pr-2 space-y-3 scrollbar-thin scrollbar-thumb-white/10">
              
              {validData.map((doc: any, idx: number) => {
                const isExpanded = activeReport === doc.period;
                return (
                <div 
                  key={idx} 
                  onClick={() => setActiveReport(isExpanded ? null : doc.period)}
                  className={`group relative p-4 rounded-xl border transition-all cursor-pointer overflow-hidden ${isExpanded ? 'bg-white/[0.05] border-indigo-500/30' : 'bg-white/[0.02] border-white/5 hover:bg-white/[0.05]'}`}
                >
                  <div className="absolute inset-0 bg-gradient-to-r from-transparent to-indigo-500/5 opacity-0 group-hover:opacity-100 transition-opacity" />
                  <div className="relative flex justify-between items-center">
                    <div>
                      <h4 className="text-white font-medium mb-1">{doc.period}</h4>
                      <div className="flex gap-3 text-xs">
                        <span className="text-slate-400">Acc: {(doc.confidence*100).toFixed(0)}%</span>
                        <span className="text-slate-400">Checks: {doc.checks_passed}/{doc.total_checks}</span>
                      </div>
                    </div>
                    {doc.red_flags_count > 0 ? (
                      <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-rose-500/10 border border-rose-500/20 text-rose-400 text-xs font-semibold">
                        <AlertOctagon className="w-3.5 h-3.5" />
                        {doc.red_flags_count} FLAGS
                      </div>
                    ) : (
                      <div className="px-2.5 py-1 rounded-md bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 text-xs font-semibold">
                        CLEAN
                      </div>
                    )}
                  </div>
                  
                  {isExpanded && (
                    <motion.div 
                      initial={{ opacity: 0, height: 0 }} 
                      animate={{ opacity: 1, height: 'auto' }} 
                      exit={{ opacity: 0, height: 0 }}
                      className="mt-4 pt-4 border-t border-white/10 space-y-3"
                    >
                      <div className="text-xs font-semibold text-slate-500 uppercase tracking-widest mb-2">Deterministic Audit Checks</div>
                      {doc.aggregate_checks?.map((check: any, cIdx: number) => (
                        <div key={cIdx} className="bg-black/20 p-3 rounded-lg border border-white/5">
                          <div className="flex justify-between items-start mb-1">
                            <span className="text-sm font-medium text-slate-200">{check.name}</span>
                            {check.passed ? (
                              <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                            ) : (
                              <ShieldAlert className="w-4 h-4 text-rose-400" />
                            )}
                          </div>
                          <div className="flex justify-between text-xs text-slate-400 font-mono">
                            <span>Δ = ${check.difference === 0 ? "0.00" : check.difference?.toFixed(2) || "N/A"}</span>
                            <span>{check.passed ? "PASS" : "FAIL"}</span>
                          </div>
                          {!check.passed && check.details && (
                            <div className="mt-2 text-xs text-rose-400/80 pl-2 border-l border-rose-500/30">
                              {check.details[0]}
                            </div>
                          )}
                        </div>
                      ))}
                      {(!doc.aggregate_checks || doc.aggregate_checks.length === 0) && (
                        <div className="text-sm text-slate-500 italic">No checks ran or data missing.</div>
                      )}
                    </motion.div>
                  )}
                </div>
              )})}

            </div>
          </motion.div>

        </div>

        {/* Detailed Findings Table */}
        <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.7 }}
          className="mt-8 bg-white/[0.02] border border-white/5 rounded-3xl p-8 backdrop-blur-xl">
          <div className="mb-6 flex justify-between items-center">
            <div>
              <h2 className="text-xl font-medium text-white flex items-center gap-2">
                <ShieldAlert className="w-5 h-5 text-rose-400" />
                Unapproved Checks & Anomalies
              </h2>
              <p className="text-sm text-slate-400 mt-1">Specific findings surfaced deterministically by the Swarm.</p>
            </div>
          </div>
          
          <div className="overflow-x-auto rounded-xl border border-white/10">
            <table className="w-full text-left text-sm text-slate-300">
              <thead className="text-xs uppercase bg-[#0A0A0B] text-slate-500 border-b border-white/10">
                <tr>
                  <th className="px-6 py-4">Period</th>
                  <th className="px-6 py-4">Anomaly Type</th>
                  <th className="px-6 py-4">Description</th>
                  <th className="px-6 py-4">Amount</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/5 bg-[#121215]">
                {validData
                  .filter((d: any) => d.red_flags_count > 0 && d.detailed_flags)
                  .flatMap((d: any) => [
                    ...(d.detailed_flags.unapproved_checks || []).map((flag: any) => ({
                      period: d.period,
                      type: 'Unapproved Check',
                      description: `Check ${flag.description} - ${flag.flag}`,
                      amount: flag.amount,
                      color: 'text-rose-400'
                    })),
                    ...(d.detailed_flags.pending_invoices || []).map((flag: any) => ({
                      period: d.period,
                      type: 'Pending ACH/Stale Invoice',
                      description: `Vendor: ${flag.vendor_name} (${flag.payment_type})`,
                      amount: flag.amount,
                      color: 'text-orange-400'
                    }))
                  ])
                  .sort((a: any, b: any) => b.amount - a.amount)
                  .map((finding: any, idx: number) => (
                    <tr key={idx} className="hover:bg-white/[0.02] transition-colors">
                      <td className="px-6 py-4 whitespace-nowrap font-medium text-white">{finding.period}</td>
                      <td className="px-6 py-4">
                        <span className={`px-2 py-1 rounded text-xs font-medium border border-current ${finding.color} bg-current/10 border-opacity-20`}>
                          {finding.type}
                        </span>
                      </td>
                      <td className="px-6 py-4 text-slate-400">{finding.description}</td>
                      <td className={`px-6 py-4 font-mono font-medium ${finding.color}`}>
                        ${finding.amount.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                      </td>
                    </tr>
                ))}
                {validData.every((d: any) => d.red_flags_count === 0) && (
                  <tr>
                    <td colSpan={4} className="px-6 py-12 text-center text-slate-500">
                      No anomalies detected in the parsed dataset.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </motion.div>

        {/* --- PORTFOLIO: HOMEOWNER LEDGER ANOMALIES --- */}
        <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.8 }}
          className="mt-8 bg-white/[0.02] border border-white/5 rounded-3xl p-8 backdrop-blur-xl">
          <div className="mb-6 flex justify-between items-center">
            <div>
              <h2 className="text-xl font-medium text-white flex items-center gap-2">
                <Users className="w-5 h-5 text-indigo-400" />
                Homeowner Ledger Anomalies & Pre-Paids
              </h2>
              <p className="text-sm text-slate-400 mt-1">
                Deterministic detection of structural billing flaws. Identifies homeowners who overpaid or have negative balances but were still double-charged (resulting in interest-free loans to the HOA).
              </p>
            </div>
          </div>
          
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {validData
              .filter((d: any) => d.homeowner_results?.failures?.length > 0)
              .flatMap((d: any) => d.homeowner_results.failures.map((f: any) => ({ ...f, period: d.period })))
              .map((failure: any, idx: number) => (
                <div key={idx} className="bg-[#0A0A0B] border border-white/10 rounded-xl p-5 hover:border-indigo-500/30 transition-colors">
                  <div className="flex justify-between items-start mb-3">
                    <div className="text-xs font-semibold text-slate-400 uppercase tracking-widest">{failure.period}</div>
                    <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-indigo-500/10 text-indigo-400 border border-indigo-500/20">
                      LEDGER MISMATCH
                    </span>
                  </div>
                  <div className="font-medium text-white mb-1">{failure.homeowner_name || "Unknown Owner"} <span className="text-slate-500 text-sm">({failure.unit_id})</span></div>
                  <div className="text-sm text-slate-400 mb-4">
                    The Swarm calculated an ending balance of <span className="text-rose-400">${failure.computed_ending.toFixed(2)}</span>, but the PM system billed actual ending at <span className="text-white">${failure.actual_ending.toFixed(2)}</span>.
                  </div>
                  {failure.has_prepaid_carryforward && (
                    <div className="text-xs bg-amber-500/10 text-amber-400 px-3 py-2 rounded-md border border-amber-500/20">
                      <strong>AI Insight:</strong> Likely structural double-charge. Homeowner padded annual fee but system failed to carryforward credit.
                    </div>
                  )}
                </div>
            ))}
            {validData.every((d: any) => !d.homeowner_results?.failures || d.homeowner_results.failures.length === 0) && (
              <div className="col-span-full p-8 text-center border border-white/5 rounded-xl bg-white/[0.01] text-slate-500">
                Data pipeline actively scanning for ledger anomalies...
              </div>
            )}
          </div>
        </motion.div>

        {/* --- PORTFOLIO: LESSONS LEARNED / ARCHITECTURAL AXIOMS --- */}
        <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.9 }}
          className="mt-8 bg-gradient-to-r from-indigo-900/10 to-cyan-900/10 border border-indigo-500/20 rounded-3xl p-8 backdrop-blur-xl mb-24">
          <div className="mb-6">
            <h2 className="text-xl font-medium text-white flex items-center gap-2">
              <Lightbulb className="w-5 h-5 text-cyan-400" />
              Architectural Axioms & Lessons Learned
            </h2>
            <p className="text-sm text-slate-400 mt-1">The difference between a Chat Wrapper and an Enterprise AI System.</p>
          </div>
          <div className="space-y-4">
            
            <div className="p-4 bg-[#0A0A0B]/50 border border-white/5 rounded-xl">
              <h4 className="font-medium text-white mb-1">1. Anomaly-First Extraction (Margin Protection)</h4>
              <p className="text-sm text-slate-400">
                To run an AI audit at scale (10,000+ HOAs), unit economics are critical. The Swarm is intentionally designed <strong>not</strong> to parse the standard 150-line operational budget. By restricting the LLM purely to extracting unapproved checks and mathematical anomalies, we cut output token costs by 95%, processing 45-page financial PDFs for roughly $0.10 computing cost per run.
              </p>
            </div>

            <div className="p-4 bg-[#0A0A0B]/50 border border-white/5 rounded-xl">
              <h4 className="font-medium text-white mb-1">2. "The Sandwich Pattern" (Speed & Determinism)</h4>
              <p className="text-sm text-slate-400">
                LLMs are highly capable at unstructured vision parsing (reading messy check images), but they are fundamentally unreliable at mathematics. The pipeline "sandwiches" the AI: Anthropic extracts the entities into rigid Pydantic models, and then passes them perfectly formatted to <strong>Pure Python</strong>, which handles the deterministic ledger math in milliseconds at zero cost.
              </p>
            </div>

            <div className="p-4 bg-[#0A0A0B]/50 border border-white/5 rounded-xl">
              <h4 className="font-medium text-white mb-1">3. SHA256 PDF Content Hashing</h4>
              <p className="text-sm text-slate-400">
                End users inevitably upload the exact same financial PDF multiple times <code>Report (1).pdf</code>. Without defense mechanisms, this doubles API inference costs and pollutes the database with twin anomalies. Content-level SHA256 hashing at the Graph-entry point acts as an impenetrable shield, dropping duplicates before they ever reach the expensive LLM layer.
              </p>
            </div>

          </div>
        </motion.div>

      </div>
    </div>
  );
}
