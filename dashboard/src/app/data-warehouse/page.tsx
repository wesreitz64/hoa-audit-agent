"use client";

import React, { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import { 
  Database,
  ArrowLeft,
  Search,
  DollarSign,
  TrendingDown,
  Activity
} from 'lucide-react';

export default function DataWarehouse() {
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [selectedPeriod, setSelectedPeriod] = useState<string>('');
  
  // New State for Vendor View
  const [viewMode, setViewMode] = useState<'month' | 'vendor'>('month');
  const [selectedVendor, setSelectedVendor] = useState<string>('ALL');
  
  // Date Filtering
  const [startDate, setStartDate] = useState('');
  const [endDate, setEndDate] = useState('');

  // Column Sorting
  const [sortConfig, setSortConfig] = useState<{key: string, direction: 'asc' | 'desc'} | null>(null);

  const requestSort = (key: string) => {
    let direction: 'asc' | 'desc' = 'asc';
    if (sortConfig && sortConfig.key === key && sortConfig.direction === 'asc') {
      direction = 'desc';
    }
    setSortConfig({ key, direction });
  };

  useEffect(() => {
    fetch('/api/vendor-ytd-report')
      .then(res => res.json())
      .then(json => {
        setData(json);
        
        // Auto-select the most recent period chronologically if available
        const periods = Array.from(new Set(json.incomeStatements?.map((i: any) => i.period)))
          .filter(Boolean)
          .sort((a: any, b: any) => {
            const dateA = new Date(`1 ${a}`).getTime();
            const dateB = new Date(`1 ${b}`).getTime();
            return dateB - dateA;
          });
          
        if (periods.length > 0) {
          setSelectedPeriod(String(periods[0]));
        }

        // Extract and sort vendors for the new view
        const vendors = Array.from(new Set(json.vendorInvoices?.map((v: any) => v.vendor_name)))
          .filter(Boolean)
          .sort();
        if (vendors.length > 0) {
          setSelectedVendor(String(vendors[0]));
        }
        
        setLoading(false);
      });
  }, []);

  if (loading || !data) {
    return (
      <div className="min-h-screen bg-slate-50 flex items-center justify-center text-slate-600">
        <div className="flex flex-col items-center gap-4">
          <Database className="w-12 h-12 animate-pulse text-cyan-500/50" />
          <p className="text-sm uppercase tracking-widest">Querying Data Warehouse...</p>
        </div>
      </div>
    );
  }

  // Extract available periods and sort them chronologically descending
  const availablePeriods = Array.from(new Set(data.incomeStatements?.map((i: any) => i.period)))
    .filter(Boolean)
    .sort((a: any, b: any) => {
      const dateA = new Date(`1 ${a}`).getTime();
      const dateB = new Date(`1 ${b}`).getTime();
      return dateB - dateA;
    });

  const availableVendors = Array.from(new Set(data.vendorInvoices?.map((v: any) => v.vendor_name))).filter(Boolean).sort();

  // Filter Data based on Modes
  const filteredIncome = viewMode === 'month' ? (data.incomeStatements?.filter((i: any) => i.period === selectedPeriod) || []) : [];
  const filteredVendorsByMonth = viewMode === 'month' ? (data.vendorInvoices?.filter((v: any) => v.period === selectedPeriod) || []) : [];
  
  const incomeCategories = filteredIncome.filter((i: any) => i.type === 'INCOME');
  const expenseCategories = filteredIncome.filter((i: any) => i.type === 'EXPENSE');

  // Vendor History mode data
  let vendorHistory = viewMode === 'vendor' 
    ? (selectedVendor === 'ALL' 
        ? (data.vendorInvoices || [])
        : (data.vendorInvoices?.filter((v: any) => v.vendor_name === selectedVendor) || []))
    : [];

  if (viewMode === 'vendor') {
    if (search) {
      const s = search.toLowerCase();
      vendorHistory = vendorHistory.filter((v: any) => 
        (v.gl_account_code || '').toLowerCase().includes(s) || 
        (v.vendor_name || '').toLowerCase().includes(s) ||
        (v.gl_account_name || '').toLowerCase().includes(s)
      );
    }
    if (startDate) {
      vendorHistory = vendorHistory.filter((v: any) => {
        const itemDate = new Date(v.invoice_date || `1 ${v.period}`).getTime();
        const start = new Date(startDate).getTime();
        return itemDate >= start;
      });
    }
    if (endDate) {
      vendorHistory = vendorHistory.filter((v: any) => {
        const itemDate = new Date(v.invoice_date || `1 ${v.period}`).getTime();
        // Add one day to end date to make it fully inclusive if they pick the exact day
        const end = new Date(endDate).getTime() + 86400000;
        return itemDate <= end;
      });
    }
    
    if (sortConfig) {
      vendorHistory.sort((a: any, b: any) => {
        let valA = a[sortConfig.key];
        let valB = b[sortConfig.key];
        
        // Date parsing for sort keys
        if (sortConfig.key === 'invoice_date' || sortConfig.key === 'paid_date' || sortConfig.key === 'period') {
          valA = new Date(valA || `1 ${a.period}`).getTime();
          valB = new Date(valB || `1 ${b.period}`).getTime();
        }
        
        if (valA < valB) return sortConfig.direction === 'asc' ? -1 : 1;
        if (valA > valB) return sortConfig.direction === 'asc' ? 1 : -1;
        return 0;
      });
    } else {
      // Default chronological descending
      vendorHistory.sort((a: any, b: any) => 
        new Date(b.invoice_date || `1 ${b.period}`).getTime() - new Date(a.invoice_date || `1 ${a.period}`).getTime()
      );
    }
  }

  const SortIcon = ({ columnKey }: { columnKey: string }) => {
    if (!sortConfig || sortConfig.key !== columnKey) return null;
    return sortConfig.direction === 'asc' ? <span className="ml-1 inline-block">↑</span> : <span className="ml-1 inline-block">↓</span>;
  };

  return (
    <div className="min-h-screen bg-slate-50 text-slate-800 font-sans selection:bg-cyan-500/30 pb-24 print:bg-white print:text-black print:p-0 print:m-0">
      
      <div className="fixed inset-0 overflow-hidden pointer-events-none print:hidden">
        <div className="absolute top-[-20%] right-[-10%] w-[50%] h-[50%] rounded-full bg-blue-100/50 blur-[120px]" />
      </div>

      <div className="relative max-w-7xl mx-auto px-6 py-12 print:max-w-none print:w-full print:px-0 print:py-0">
        
        <header className="mb-12 border-b border-slate-200 pb-8 print:mb-4 print:pb-2 print:border-b-black">
          <button onClick={() => window.location.href='/'} className="inline-flex items-center gap-2 text-sm text-slate-600 hover:text-slate-900 transition-colors mb-6 print:hidden">
            <ArrowLeft className="w-4 h-4" /> Back to Swarm Output
          </button>
          <div className="flex items-center justify-between">
            <div>
              <div className="flex items-center gap-3 mb-2">
                <div className="p-2 bg-blue-100 border border-blue-300 rounded-lg print:border-black/20 print:bg-transparent">
                  <Database className="w-6 h-6 text-blue-600 print:text-black" />
                </div>
                <h1 className="text-3xl font-light tracking-tight text-slate-900 print:text-black print:text-2xl">
                  Data Warehouse <span className="font-semibold text-transparent bg-clip-text bg-gradient-to-r from-blue-600 to-emerald-600 print:text-black print:!bg-none">Reports</span>
                </h1>
              </div>
              <p className="text-slate-600 pl-1 print:text-slate-700">
                {viewMode === 'month' 
                  ? <>Ledger Integration • Period: <strong className="text-slate-900 print:text-black">{selectedPeriod}</strong></> 
                  : <>Cross-Period Auditing • Vendor: <strong className="text-slate-900 print:text-black">{selectedVendor}</strong></>}
              </p>
            </div>
            
            <div className="flex gap-4 print:hidden items-center">
              
              {/* Tab Switcher */}
              <div className="flex bg-slate-100 p-1 rounded-lg border border-slate-200 mr-2">
                <button 
                  onClick={() => setViewMode('month')}
                  className={`px-3 py-1.5 text-xs rounded-md transition-all ${viewMode === 'month' ? 'bg-blue-100 text-blue-600' : 'text-slate-600 hover:text-slate-700'}`}
                >Month</button>
                <button 
                  onClick={() => setViewMode('vendor')}
                  className={`px-3 py-1.5 text-xs rounded-md transition-all ${viewMode === 'vendor' ? 'bg-blue-100 text-blue-600' : 'text-slate-600 hover:text-slate-700'}`}
                >Vendor</button>
              </div>

              {viewMode === 'month' ? (
                <select 
                  value={selectedPeriod}
                  onChange={(e) => setSelectedPeriod(e.target.value)}
                  className="bg-white border border-slate-200 rounded-lg px-4 py-2 text-sm text-slate-900 focus:outline-none appearance-none cursor-pointer hover:bg-slate-100 transition-colors"
                >
                  {availablePeriods.map(p => (
                    <option key={String(p)} value={String(p)}>{String(p)}</option>
                  ))}
                </select>
              ) : (
                <div className="flex items-center gap-2">
                  <select 
                    value={selectedVendor}
                    onChange={(e) => setSelectedVendor(e.target.value)}
                    className="bg-white border border-slate-200 rounded-lg px-4 py-2 text-sm text-slate-900 focus:outline-none focus:border-cyan-500/50 appearance-none cursor-pointer hover:bg-slate-100 transition-colors max-w-[200px]"
                  >
                    <option value="ALL">-- All Vendors --</option>
                    {availableVendors.map(v => (
                      <option key={String(v)} value={String(v)}>{String(v)}</option>
                    ))}
                  </select>
                  
                  <div className="h-6 w-px bg-white/10 mx-1"></div>
                  
                  <div className="flex items-center gap-2 bg-white border border-slate-200 rounded-lg px-3 py-1">
                    <input 
                      type="date" 
                      value={startDate} 
                      onChange={(e) => setStartDate(e.target.value)} 
                      className="bg-transparent text-sm text-slate-700 focus:outline-none focus:text-blue-600 [&::-webkit-calendar-picker-indicator]:invert-[0.6] cursor-pointer"
                    />
                    <span className="text-slate-600 text-xs">to</span>
                    <input 
                      type="date" 
                      value={endDate} 
                      onChange={(e) => setEndDate(e.target.value)} 
                      className="bg-transparent text-sm text-slate-700 focus:outline-none focus:text-blue-600 [&::-webkit-calendar-picker-indicator]:invert-[0.6] cursor-pointer"
                    />
                    {(startDate || endDate) && (
                      <button 
                        onClick={() => { setStartDate(''); setEndDate(''); }}
                        className="ml-2 text-red-600/70 hover:text-red-600 text-xs transition-colors"
                      >
                        Clear
                      </button>
                    )}
                  </div>
                </div>
              )}

              <button 
                onClick={() => window.print()}
                className="px-4 py-2 border border-slate-700 hover:bg-slate-800 rounded-lg text-sm transition-colors text-slate-700"
              >
                🖨️ Print Ledger
              </button>
              <div className="relative w-64 hidden md:block">
                <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-slate-600" />
                <input 
                  type="text"
                  placeholder="Search GL Codes or Vendors..."
                  value={search}
                  onChange={e => setSearch(e.target.value)}
                  className="w-full bg-slate-100 border border-slate-200 rounded-lg pl-9 pr-4 py-2 text-sm text-slate-900 focus:outline-none focus:border-cyan-500/50"
                />
              </div>
            </div>
          </div>
        </header>

        <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} 
          className="bg-white border border-slate-200 rounded-3xl overflow-hidden shadow-2xl print:shadow-none print:border-none print:bg-white print:rounded-none">
          
          <div className="p-6 bg-white shadow-sm border-slate-200 border-b border-slate-200 flex items-center justify-between print:p-2 print:border-b-black">
            <h2 className="text-lg font-medium text-slate-900 flex items-center gap-2 print:text-black">
              <Activity className="w-5 h-5 text-emerald-600 print:text-black" />
              {viewMode === 'month' ? 'Income & Expense YTD with Vendor Breakdowns' : 'Vendor Payment History Audit'}
            </h2>
          </div>

          <div className="overflow-x-auto print:overflow-visible">
            {viewMode === 'month' ? (
              <table className="w-full text-left text-sm text-slate-700 print:text-xs print:text-black border-collapse">
                <thead className="bg-slate-50 text-slate-600 uppercase text-[10px] tracking-wider sticky top-0 z-10 box-border print:bg-white print:text-black border-b border-slate-200 print:border-black">
                <tr>
                  <th className="px-6 py-4 print:px-2 print:py-2 font-semibold w-1/4">GL Category / Vendor</th>
                  <th className="px-6 py-4 print:px-2 print:py-2 font-semibold text-right">Month Actual</th>
                  <th className="px-6 py-4 print:px-2 print:py-2 font-semibold text-right">Month Budget</th>
                  <th className="px-6 py-4 print:px-2 print:py-2 font-semibold text-right">YTD Actual</th>
                  <th className="px-6 py-4 print:px-2 print:py-2 font-semibold text-right">Annual Budget</th>
                  <th className="px-6 py-4 print:px-2 print:py-2 font-semibold text-right">Variance</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/5 print:divide-black/20">
                
                {/* --- EXPENSES --- */}
                <tr><td colSpan={6} className="bg-slate-50 border-slate-200 px-6 py-3 print:px-2 print:py-2 text-xs font-bold text-red-600 uppercase tracking-widest print:text-black print:bg-gray-100">Operating Expenses</td></tr>
                
                {expenseCategories
                  .filter((inc: any) => inc.category.toLowerCase().includes(search.toLowerCase()) || search === '')
                  .map((inc: any, idx: number) => {
                    const variance = inc.annual_budget - inc.ytd_actual;
                    
                    // Find matching vendors for this GL Code natively within this period
                    const matchingVendors = filteredVendorsByMonth.filter((v: any) => 
                      v.gl_account_code?.includes(inc.gl_code) || 
                      v.gl_account_name?.toLowerCase() === inc.category.toLowerCase()
                    );
                    
                    return (
                      <React.Fragment key={`exp-${idx}`}>
                        <tr className="hover:bg-white shadow-sm border-slate-200 transition-colors group print:break-inside-avoid">
                          <td className="px-6 py-4 print:px-2 print:py-2">
                            <span className="font-medium text-slate-900 print:text-black mr-2">{inc.gl_code || "---"}</span>
                            <span className="print:text-black">{inc.category}</span>
                          </td>
                          <td className="px-6 py-4 print:px-2 print:py-2 text-right font-mono text-slate-900 print:text-black">
                            ${(inc.month_actual || 0).toLocaleString(undefined, {minimumFractionDigits:2, maximumFractionDigits:2})}
                          </td>
                          <td className="px-6 py-4 print:px-2 print:py-2 text-right font-mono text-slate-600 print:text-black">
                            ${(inc.month_budget || 0).toLocaleString(undefined, {minimumFractionDigits:2, maximumFractionDigits:2})}
                          </td>
                          <td className="px-6 py-4 print:px-2 print:py-2 text-right font-mono text-blue-700 print:text-black">
                            ${inc.ytd_actual.toLocaleString(undefined, {minimumFractionDigits:2, maximumFractionDigits:2})}
                          </td>
                          <td className="px-6 py-4 print:px-2 print:py-2 text-right font-mono text-slate-600 print:text-black">
                            ${(inc.annual_budget || 0).toLocaleString(undefined, {minimumFractionDigits:2, maximumFractionDigits:2})}
                          </td>
                          <td className={`px-6 py-4 print:px-2 print:py-2 text-right font-mono print:text-black ${variance < 0 ? 'text-red-600' : 'text-emerald-600'}`}>
                            {variance < 0 && "-"}
                            ${Math.abs(variance).toLocaleString(undefined, {minimumFractionDigits:2, maximumFractionDigits:2})}
                          </td>
                        </tr>
                        
                        {/* Nested Vendor Rows */}
                        {matchingVendors.map((v: any, vIdx: number) => (
                          <tr key={`v-${idx}-${vIdx}`} className="bg-slate-50 print:bg-transparent print:break-inside-avoid">
                            <td className="px-6 py-2 pl-12 print:px-2 print:pl-6 text-xs flex items-center gap-2">
                              <TrendingDown className="w-3 h-3 text-slate-600 print:text-black" />
                              <span className="text-blue-600 print:text-black">{v.vendor_name}</span>
                              <span className="text-slate-500 print:text-slate-700 text-[10px] ml-2">({v.payment_type} / {v.invoice_date})</span>
                            </td>
                            <td className="px-6 py-2 print:px-2 print:py-1 text-right font-mono text-xs text-red-600 print:text-black">
                              -${v.amount.toLocaleString(undefined, {minimumFractionDigits:2, maximumFractionDigits:2})}
                            </td>
                            <td className="px-6 py-2 print:px-2"></td>
                            <td className="px-6 py-2 print:px-2"></td>
                            <td className="px-6 py-2 print:px-2"></td>
                            <td className="px-6 py-2 print:px-2"></td>
                          </tr>
                        ))}
                      </React.Fragment>
                  )})}
                  
              </tbody>
            </table>
            ) : (
              <table className="w-full text-left text-sm text-slate-700 print:text-xs print:text-black border-collapse">
                <thead className="bg-slate-50 text-slate-600 uppercase text-[10px] tracking-wider sticky top-0 z-10 box-border print:bg-white print:text-black border-b border-slate-200 print:border-black">
                  <tr>
                    <th className="px-6 py-4 print:px-2 print:py-2 font-semibold cursor-pointer hover:bg-slate-100 select-none transition-colors" onClick={() => requestSort('invoice_date')}>
                      Invoice Date <SortIcon columnKey="invoice_date" />
                    </th>
                    <th className="px-6 py-4 print:px-2 print:py-2 font-semibold cursor-pointer hover:bg-slate-100 select-none transition-colors" onClick={() => requestSort('paid_date')}>
                      Paid Date <SortIcon columnKey="paid_date" />
                    </th>
                    <th className="px-6 py-4 print:px-2 print:py-2 font-semibold cursor-pointer hover:bg-slate-100 select-none transition-colors" onClick={() => requestSort('vendor_name')}>
                      Vendor <SortIcon columnKey="vendor_name" />
                    </th>
                    <th className="px-6 py-4 print:px-2 print:py-2 font-semibold cursor-pointer hover:bg-slate-100 select-none transition-colors" onClick={() => requestSort('period')}>
                      Accounting Period <SortIcon columnKey="period" />
                    </th>
                    <th className="px-6 py-4 print:px-2 print:py-2 font-semibold cursor-pointer hover:bg-slate-100 select-none transition-colors" onClick={() => requestSort('gl_account_name')}>
                      GL Account <SortIcon columnKey="gl_account_name" />
                    </th>
                    <th className="px-6 py-4 print:px-2 print:py-2 font-semibold cursor-pointer hover:bg-slate-100 select-none transition-colors" onClick={() => requestSort('payment_type')}>
                      Type <SortIcon columnKey="payment_type" />
                    </th>
                    <th className="px-6 py-4 print:px-2 print:py-2 font-semibold text-right cursor-pointer hover:bg-slate-100 select-none transition-colors" onClick={() => requestSort('amount')}>
                      Amount <SortIcon columnKey="amount" />
                    </th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-white/5 print:divide-black/20">
                  {vendorHistory.map((invoice: any, idx: number) => (
                    <tr key={`vh-${idx}`} className="hover:bg-white shadow-sm border-slate-200 transition-colors print:break-inside-avoid">
                      <td className="px-6 py-4 print:px-2 print:py-2 text-slate-900 font-mono print:text-black">{invoice.invoice_date || 'N/A'}</td>
                      <td className="px-6 py-4 print:px-2 print:py-2 text-blue-600/80 font-mono print:text-black">{invoice.paid_date || 'N/A'}</td>
                      <td className="px-6 py-4 print:px-2 print:py-2 text-slate-900 font-medium print:text-black">{invoice.vendor_name || '---'}</td>
                      <td className="px-6 py-4 print:px-2 print:py-2 text-emerald-600 print:text-black">{invoice.period}</td>
                      <td className="px-6 py-4 print:px-2 print:py-2">
                        <span className="font-medium text-slate-700 print:text-black mr-2">{invoice.gl_account_code}</span>
                        <span className="text-slate-500 print:text-slate-700">{invoice.gl_account_name}</span>
                      </td>
                      <td className="px-6 py-4 print:px-2 print:py-2 text-blue-700 print:text-black font-mono text-xs">{invoice.payment_type}</td>
                      <td className="px-6 py-4 print:px-2 print:py-2 text-right font-mono text-red-600 print:text-black">
                        ${invoice.amount.toLocaleString(undefined, {minimumFractionDigits:2, maximumFractionDigits:2})}
                      </td>
                    </tr>
                  ))}
                  {vendorHistory.length === 0 && (
                    <tr>
                      <td colSpan={7} className="px-6 py-8 text-center text-slate-600 italic">No historical invoices found.</td>
                    </tr>
                  )}
                  {vendorHistory.length > 0 && (
                    <tr className="bg-white shadow-sm border-slate-200 print:bg-gray-100">
                      <td colSpan={6} className="px-6 py-4 text-right font-semibold text-slate-900 print:text-black uppercase text-xs tracking-wider">Total Value Processed</td>
                      <td className="px-6 py-4 text-right font-mono font-bold text-red-600 print:text-black text-lg">
                        ${vendorHistory.reduce((sum: number, v: any) => sum + (v.amount || 0), 0).toLocaleString(undefined, {minimumFractionDigits:2, maximumFractionDigits:2})}
                      </td>
                    </tr>
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
