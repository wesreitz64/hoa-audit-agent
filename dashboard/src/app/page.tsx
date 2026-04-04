"use client";

import React, { useState, useMemo } from 'react';
import { motion } from 'framer-motion';
import { 
  ShieldAlert, 
  BrainCircuit, 
  CheckCircle2, 
  FileSearch,
  AlertOctagon,
  ChevronRight
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

  // Ensure periods are sorted correctly (chronologically)
  // We'll write a quick sort assuming format "Month YYYY"
  const monthOrder: Record<string, number> = {
    "January": 1, "February": 2, "March": 3, "April": 4, 
    "May": 5, "June": 6, "July": 7, "August": 8, 
    "September": 9, "October": 10, "November": 11, "December": 12
  };

  // Fetch the latest generated Python pipeline data securely via the API
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

  // Process data purely for UI
  const processedData = useMemo(() => {
    if (!rawAuditData || rawAuditData.length === 0) return null;

    // Filter out unknown periods and skipped_duplicates
    let validData = rawAuditData.filter(d => 
      d.status === "complete" && d.period !== "Unknown"
    );

    // Deduplicate by strict period name (so "February 2026" only mounts once)
    const seenPeriods = new Set<string>();
    validData = validData.filter(d => {
      if (seenPeriods.has(d.period)) return false;
      seenPeriods.add(d.period);
      return true;
    });

    // Sort chronologically
    validData.sort((a, b) => {
      const [mA, yA] = a.period.split(' ');
      const [mB, yB] = b.period.split(' ');
      if (yA !== yB) return parseInt(yA) - parseInt(yB);
      return monthOrder[mA] - monthOrder[mB];
    });

    // Aggregates
    const totalFiles = validData.length;
    const totalChecks = validData.reduce((acc, curr) => acc + curr.total_checks, 0);
    const passedChecks = validData.reduce((acc, curr) => acc + curr.checks_passed, 0);
    const totalRedFlags = validData.reduce((acc, curr) => acc + curr.red_flags, 0);
    const avgConfidence = validData.reduce((acc, curr) => acc + curr.confidence, 0) / (totalFiles || 1);

    // Map for charting
    const chartData = validData.map(d => ({
      name: d.period.replace(' 202', ' \'2'), // e.g. "February '26"
      flags: d.red_flags,
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
      
      {/* Decorative Background */}
      <div className="fixed inset-0 overflow-hidden pointer-events-none">
        <div className="absolute top-[-20%] left-[-10%] w-[50%] h-[50%] rounded-full bg-indigo-900/10 blur-[120px]" />
        <div className="absolute bottom-[-20%] right-[-10%] w-[50%] h-[50%] rounded-full bg-rose-900/10 blur-[120px]" />
      </div>

      <div className="relative max-w-7xl mx-auto px-6 py-12">
        
        {/* Header */}
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
            <div className="text-sm text-slate-500 uppercase tracking-widest font-semibold mb-1">Status</div>
            <div className="flex items-center gap-2">
              <span className="relative flex h-3 w-3">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
                <span className="relative inline-flex rounded-full h-3 w-3 bg-emerald-500"></span>
              </span>
              <span className="text-emerald-400 font-medium">System Online</span>
            </div>
          </div>
        </header>

        {/* KPIs */}
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
          
          {/* Chart Section */}
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

          {/* Document Feed */}
          <motion.div initial={{ opacity: 0, x: 20 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: 0.6 }}
            className="bg-white/[0.02] border border-white/10 rounded-3xl p-6 backdrop-blur-md flex flex-col h-full">
            <h2 className="text-xl font-medium text-white mb-6">Audit Reports</h2>
            <div className="flex-1 overflow-y-auto pr-2 space-y-3 scrollbar-thin scrollbar-thumb-white/10">
              
              {validData.map((doc: any, idx: number) => (
                <div 
                  key={idx} 
                  className="group relative p-4 rounded-xl bg-white/[0.02] border border-white/5 hover:bg-white/[0.05] transition-all cursor-pointer overflow-hidden"
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
                    {doc.red_flags > 0 ? (
                      <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-rose-500/10 border border-rose-500/20 text-rose-400 text-xs font-semibold">
                        <AlertOctagon className="w-3.5 h-3.5" />
                        {doc.red_flags} FLAGS
                      </div>
                    ) : (
                      <div className="px-2.5 py-1 rounded-md bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 text-xs font-semibold">
                        CLEAN
                      </div>
                    )}
                  </div>
                </div>
              ))}

            </div>
          </motion.div>

        </div>
      </div>
    </div>
  );
}
