"use client";

import React, { useState, useEffect, useMemo } from 'react';
import { motion } from 'framer-motion';
import { 
  Users,
  ArrowLeft,
  Search,
  Activity,
  History,
  AlertTriangle
} from 'lucide-react';

// Helper to parse 'January 2025' into a sortable integer (e.g., 202501)
const parsePeriod = (periodStr: string) => {
  const [month, year] = periodStr.split(' ');
  const months: Record<string, string> = {
    'January': '01', 'February': '02', 'March': '03', 'April': '04',
    'May': '05', 'June': '06', 'July': '07', 'August': '08',
    'September': '09', 'October': '10', 'November': '11', 'December': '12'
  };
  return parseInt(`${year}${months[month] || '00'}`);
};

export default function HomeownersPage() {
  const [records, setRecords] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [viewMode, setViewMode] = useState<'trace' | 'delinquency'>('trace');
  const [selectedUnit, setSelectedUnit] = useState<string>('');
  const [search, setSearch] = useState('');
  const [startPeriod, setStartPeriod] = useState<string>('');
  const [endPeriod, setEndPeriod] = useState<string>('');
  
  // Combobox state
  const [accountDropdownOpen, setAccountDropdownOpen] = useState(false);
  const [accountQuery, setAccountQuery] = useState('');

  useEffect(() => {
    fetch('/api/homeowner-records')
      .then(res => res.json())
      .then(json => {
        if (json.records) {
          setRecords(json.records);
          const units = Array.from(new Set(json.records.map((r: any) => r.unit_id))).sort() as string[];
          if (units.length > 0) setSelectedUnit(units[0]);
        }
        setLoading(false);
      });
  }, []);

  // Compute available units with names
  const availableUnits = useMemo(() => {
    const map = new Map<string, string>();
    records.forEach(r => {
      if (!map.has(r.unit_id)) map.set(r.unit_id, r.homeowner_name);
    });
    // Sort by Resident Name alphabetically instead of Unit ID
    return Array.from(map.entries()).sort((a, b) => a[1].localeCompare(b[1]));
  }, [records]);

  // Compute strictly chronological periods for the delinquency matrix
  const allPeriods = useMemo(() => {
    const periods = Array.from(new Set(records.map(r => r.period))).filter(Boolean);
    return periods.sort((a, b) => parsePeriod(a) - parsePeriod(b));
  }, [records]);

  if (loading) {
    return (
      <div className="min-h-screen bg-slate-50 flex items-center justify-center text-slate-600">
        <div className="flex flex-col items-center gap-4">
          <Users className="w-12 h-12 animate-pulse text-indigo-500/50" />
          <p className="text-sm uppercase tracking-widest">Compiling Resident Data...</p>
        </div>
      </div>
    );
  }

  // --- TRACE MODE DATA ---
  let traceData = records.filter(r => r.unit_id === selectedUnit);
  if (startPeriod) {
    traceData = traceData.filter(r => parsePeriod(r.period) >= parsePeriod(startPeriod));
  }
  if (endPeriod) {
    traceData = traceData.filter(r => parsePeriod(r.period) <= parsePeriod(endPeriod));
  }
  traceData = traceData.sort((a, b) => parsePeriod(a.period) - parsePeriod(b.period));

  // --- DELINQUENCY MAP DATA ---
  // Create a matrix: unit_id -> { [period]: ending_balance }
  let delinquencyMap = new Map<string, any>();
  records.forEach(r => {
    if (!delinquencyMap.has(r.unit_id)) {
      delinquencyMap.set(r.unit_id, { unit_id: r.unit_id, name: r.homeowner_name, total_delinquent_months: 0, _balances: {} });
    }
    const row = delinquencyMap.get(r.unit_id);
    row._balances[r.period] = r.ending_balance;
    if (r.ending_balance > 0) row.total_delinquent_months += 1;
  });

  // Filter to only those who have had a balance > 0 at ANY point, or via search
  let delinquencyRows = Array.from(delinquencyMap.values());
  if (search) {
    const s = search.toLowerCase();
    delinquencyRows = delinquencyRows.filter(r => r.unit_id.toLowerCase().includes(s) || r.name.toLowerCase().includes(s));
  } else {
    // Default show only units with any delinquency history
    delinquencyRows = delinquencyRows.filter(r => r.total_delinquent_months > 0);
  }
  // Sort by highest average delinquency or most frequent
  delinquencyRows.sort((a, b) => b.total_delinquent_months - a.total_delinquent_months);

  return (
    <div className="min-h-screen bg-[#F8FAFC] text-slate-800 font-sans selection:bg-indigo-500/30 pb-24">
      
      <div className="fixed inset-0 overflow-hidden pointer-events-none print:hidden">
        <div className="absolute top-[-20%] left-[-10%] w-[50%] h-[50%] rounded-full bg-indigo-100/40 blur-[120px]" />
      </div>

      <div className="relative max-w-7xl mx-auto px-6 py-12">
        
        <header className="mb-12 border-b border-slate-200 pb-8 hover:border-slate-300 transition-colors">
          <button onClick={() => window.location.href='/'} className="inline-flex items-center gap-2 text-sm text-slate-500 hover:text-indigo-600 transition-colors mb-6 font-medium">
            <ArrowLeft className="w-4 h-4" /> Back to Dashboard
          </button>
          
          <div className="flex flex-col md:flex-row items-start md:items-end justify-between gap-6">
            <div>
              <div className="flex items-center gap-3 mb-2">
                <div className="p-2.5 bg-indigo-50 border border-indigo-200 rounded-xl shadow-sm">
                  <Users className="w-6 h-6 text-indigo-600" />
                </div>
                <h1 className="text-3xl font-light tracking-tight text-slate-900">
                  Homeowner <span className="font-semibold text-transparent bg-clip-text bg-gradient-to-r from-indigo-600 to-violet-600">AR Auditing</span>
                </h1>
              </div>
              <p className="text-slate-500 pl-1 drop-shadow-sm">
                Deterministic 14-month historical account tracking and delinquency mapping
              </p>
            </div>
            
            <div className="flex gap-4 items-center">
              {/* Tab Switcher */}
              <div className="flex bg-white/60 backdrop-blur p-1 rounded-xl border border-slate-200 shadow-sm">
                <button 
                  onClick={() => setViewMode('trace')}
                  className={`px-4 py-2 text-sm font-medium rounded-lg transition-all flex border border-transparent items-center gap-2
                    ${viewMode === 'trace' ? 'bg-white shadow-sm border-slate-200 text-indigo-600' : 'text-slate-500 hover:text-slate-700'}`}
                >
                  <History className="w-4 h-4" /> Ledger Trace
                </button>
                <button 
                  onClick={() => setViewMode('delinquency')}
                  className={`px-4 py-2 text-sm font-medium rounded-lg transition-all flex items-center border border-transparent gap-2
                    ${viewMode === 'delinquency' ? 'bg-white shadow-sm border-slate-200 text-red-600' : 'text-slate-500 hover:text-slate-700'}`}
                >
                  <Activity className="w-4 h-4" /> Delinquency Map
                </button>
              </div>
            </div>
          </div>
        </header>

        <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} 
          className="bg-white/80 backdrop-blur-sm border border-slate-200/80 rounded-3xl overflow-hidden shadow-xl shadow-slate-200/50">
          
          <div className="p-6 bg-white shadow-sm border-b border-slate-100 flex flex-col md:flex-row items-center justify-between gap-4">
            
            <div className="flex items-center gap-4">
              {viewMode === 'trace' ? (
                <>
                  <div className="flex flex-col relative w-[300px]">
                    <label className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-1">Target Account</label>
                    <div 
                      className="bg-slate-50 border border-slate-200 shadow-inner rounded-xl px-4 py-2.5 text-sm font-medium text-slate-800 cursor-pointer flex justify-between items-center"
                      onClick={() => { setAccountDropdownOpen(!accountDropdownOpen); setAccountQuery(''); }}
                    >
                      <span className="truncate">
                        {selectedUnit ? `${availableUnits.find(u => u[0] === selectedUnit)?.[1] || ''} (${selectedUnit})` : 'Select Account...'}
                      </span>
                      <svg className="w-4 h-4 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19 9l-7 7-7-7"></path></svg>
                    </div>
                    
                    {accountDropdownOpen && (
                      <>
                        <div className="absolute top-full left-0 mt-1 w-[350px] z-50 bg-white border border-slate-200 rounded-xl shadow-2xl max-h-[400px] flex flex-col overflow-hidden">
                          <div className="p-2 border-b border-slate-100 bg-slate-50/50">
                            <input 
                              autoFocus
                              type="text"
                              value={accountQuery}
                              onChange={e => setAccountQuery(e.target.value)}
                              placeholder="Type name or unit ID to search..."
                              className="w-full bg-white border border-slate-200 shadow-inner rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-indigo-400 focus:ring-2 focus:ring-indigo-100 placeholder:text-slate-400"
                            />
                          </div>
                          <div className="overflow-y-auto">
                            {availableUnits
                              .filter(([unit, name]) => 
                                unit.toLowerCase().includes(accountQuery.toLowerCase()) || 
                                name.toLowerCase().includes(accountQuery.toLowerCase())
                              )
                              .map(([unit, name]) => (
                                <div 
                                  key={unit}
                                  className="px-4 py-3 text-sm hover:bg-indigo-50 border-b border-slate-50 cursor-pointer text-slate-700 transition-colors"
                                  onClick={() => { setSelectedUnit(unit); setAccountDropdownOpen(false); }}
                                >
                                  <div className="font-semibold text-slate-800">{name}</div>
                                  <div className="text-[11px] font-mono text-slate-500 uppercase tracking-widest mt-0.5">{unit}</div>
                                </div>
                            ))}
                            {availableUnits.filter(([unit, name]) => unit.toLowerCase().includes(accountQuery.toLowerCase()) || name.toLowerCase().includes(accountQuery.toLowerCase())).length === 0 && (
                              <div className="p-4 text-center text-sm text-slate-500 italic">No matches found.</div>
                            )}
                          </div>
                        </div>
                        <div className="fixed inset-0 z-40" onClick={() => setAccountDropdownOpen(false)}></div>
                      </>
                    )}
                  </div>
                  
                  <div className="w-px h-10 bg-slate-200 mx-2 hidden lg:block"></div>
                  
                  <div className="hidden md:flex gap-4">
                    <div className="flex flex-col">
                      <label className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-1">From Period</label>
                      <select 
                        value={startPeriod}
                        onChange={(e) => setStartPeriod(e.target.value)}
                        className="bg-slate-50 border border-slate-200 shadow-inner rounded-xl px-4 py-2.5 text-sm font-medium text-slate-800 focus:outline-none focus:border-indigo-400 focus:ring-4 focus:ring-indigo-100 transition-all appearance-none cursor-pointer"
                      >
                        <option value="">-- All --</option>
                        {allPeriods.map(p => <option key={p} value={p as string}>{p}</option>)}
                      </select>
                    </div>
                    
                    <div className="flex flex-col">
                      <label className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-1">To Period</label>
                      <select 
                        value={endPeriod}
                        onChange={(e) => setEndPeriod(e.target.value)}
                        className="bg-slate-50 border border-slate-200 shadow-inner rounded-xl px-4 py-2.5 text-sm font-medium text-slate-800 focus:outline-none focus:border-indigo-400 focus:ring-4 focus:ring-indigo-100 transition-all appearance-none cursor-pointer"
                      >
                        <option value="">-- All --</option>
                        {allPeriods.map(p => <option key={p} value={p as string}>{p}</option>)}
                      </select>
                    </div>
                  </div>
                </>
              ) : (
                <div className="flex items-center gap-2">
                  <AlertTriangle className="w-5 h-5 text-red-500" />
                  <h2 className="text-lg font-medium text-slate-800">Chronic Delinquency Matrix</h2>
                </div>
              )}
            </div>

            {viewMode === 'delinquency' && (
              <div className="relative w-64">
                <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
                <input 
                  type="text"
                  placeholder="Filter name or unit ID..."
                  value={search}
                  onChange={e => setSearch(e.target.value)}
                  className="w-full bg-slate-50 border border-slate-200 shadow-inner rounded-xl pl-9 pr-4 py-2.5 text-sm text-slate-800 focus:outline-none focus:border-red-400 focus:ring-4 focus:ring-red-100 transition-all"
                />
              </div>
            )}
          </div>

          <div className="overflow-auto max-h-[70vh] p-0 [&::-webkit-scrollbar]:w-3 [&::-webkit-scrollbar]:h-3 [&::-webkit-scrollbar-track]:bg-slate-50 [&::-webkit-scrollbar-thumb]:bg-slate-300 [&::-webkit-scrollbar-thumb]:rounded-full pb-4">
            {viewMode === 'trace' ? (
              <table className="w-full text-left text-sm text-slate-700 border-collapse relative">
                <thead className="bg-slate-50 border-b border-slate-200 text-slate-500 uppercase text-[10px] tracking-widest font-semibold sticky top-0 z-30 shadow-sm">
                  <tr>
                    <th className="px-6 py-4">Accounting Period</th>
                    <th className="px-6 py-4 text-right">Prev Balance</th>
                    <th className="px-6 py-4 text-right">Billing</th>
                    <th className="px-6 py-4 text-right">Receipts</th>
                    <th className="px-6 py-4 text-right">Prepaid Credits</th>
                    <th className="px-6 py-4 text-right">Adjustments</th>
                    <th className="px-6 py-4 text-right bg-indigo-50/50 text-indigo-900 border-l border-indigo-100">Ending Balance</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {traceData.map((t, idx) => (
                    <tr key={idx} className="hover:bg-indigo-50/30 transition-colors group">
                      <td className="px-6 py-4 font-medium text-slate-800">{t.period}</td>
                      <td className="px-6 py-4 text-right font-mono text-slate-500">${t.prev_balance.toLocaleString(undefined, {minimumFractionDigits:2})}</td>
                      <td className="px-6 py-4 text-right font-mono text-slate-800">${t.billing.toLocaleString(undefined, {minimumFractionDigits:2})}</td>
                      <td className="px-6 py-4 text-right font-mono text-emerald-600">{t.receipts !== 0 ? `-$${Math.abs(t.receipts).toLocaleString(undefined, {minimumFractionDigits:2})}` : '$0.00'}</td>
                      <td className="px-6 py-4 text-right font-mono text-emerald-600/70">{t.prepaid !== 0 ? `-$${Math.abs(t.prepaid).toLocaleString(undefined, {minimumFractionDigits:2})}` : '$0.00'}</td>
                      <td className="px-6 py-4 text-right font-mono text-slate-500">{t.adjustments !== 0 ? `$${t.adjustments.toLocaleString(undefined, {minimumFractionDigits:2})}` : '$0.00'}</td>
                      <td className={`px-6 py-4 text-right font-mono font-bold border-l border-slate-100 group-hover:border-indigo-100 transition-colors
                        ${t.ending_balance > 0 ? 'text-red-600 bg-red-50/50' : t.ending_balance < 0 ? 'text-indigo-600 bg-indigo-50/50' : 'text-slate-800'}`}>
                        ${t.ending_balance.toLocaleString(undefined, {minimumFractionDigits:2})}
                      </td>
                    </tr>
                  ))}
                  {traceData.length === 0 && (
                    <tr><td colSpan={7} className="px-6 py-12 text-center text-slate-400 italic">No ledger records found for this unit.</td></tr>
                  )}
                </tbody>
              </table>
            ) : (
              <table className="w-full text-left text-sm text-slate-700 border-separate border-spacing-0">
                <thead className="bg-[#1A1F2C] text-slate-300 uppercase text-[10px] tracking-widest font-semibold sticky top-0 z-30">
                  <tr>
                    <th className="px-6 py-4 border-r border-b border-white/5 bg-[#1A1F2C] sticky left-0 z-40">Unit & Resident</th>
                    {allPeriods.map(p => {
                      const parts = p.split(' ');
                      return (
                        <th key={p} className="px-4 py-4 border-b border-white/10 text-right whitespace-nowrap min-w-[100px] bg-[#1A1F2C]">
                          {parts[0].slice(0,3)} '{parts[1].slice(-2)}
                        </th>
                      )
                    })}
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 bg-white">
                  {delinquencyRows.map((r, idx) => (
                    <tr key={idx} className="hover:bg-red-50/30 transition-colors">
                      <td className="px-6 py-3 border-r border-b border-slate-100 bg-white sticky left-0 shadow-[2px_0_5px_-2px_rgba(0,0,0,0.05)] z-20">
                        <div className="font-semibold text-slate-900">{r.unit_id} <span className="text-slate-400 font-normal ml-2">({r.total_delinquent_months} mo)</span></div>
                        <div className="text-xs text-slate-500 whitespace-nowrap overflow-hidden text-ellipsis max-w-[200px]">{r.name}</div>
                      </td>
                      {allPeriods.map(p => {
                        const bal = r._balances[p];
                        if (bal === undefined) return <td key={p} className="px-4 py-3 text-right bg-slate-50 text-slate-300 font-mono text-xs">---</td>;
                        
                        let txColor = 'text-slate-400';
                        let bgColor = '';
                        if (bal > 0) {
                          txColor = 'text-red-700 font-bold';
                          bgColor = 'bg-red-50/50';
                        } else if (bal < 0) {
                          txColor = 'text-indigo-500/80';
                        } else {
                          txColor = 'text-emerald-500/80';
                        }
                        return (
                          <td key={p} className={`px-4 py-3 border-b border-slate-100 text-right font-mono text-xs border-r border-slate-50 ${txColor} ${bgColor}`}>
                            ${bal.toLocaleString(undefined, {minimumFractionDigits:0, maximumFractionDigits:2})}
                          </td>
                        )
                      })}
                    </tr>
                  ))}
                  {delinquencyRows.length === 0 && (
                    <tr><td colSpan={allPeriods.length + 1} className="px-6 py-12 text-center text-slate-400 italic bg-white">No delinquent accounts found matching filter.</td></tr>
                  )}
                </tbody>
              </table>
            )}
          </div>
        </motion.div>

      </div>
    </div>
  );
}
