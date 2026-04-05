import re

with open('src/app/page.tsx', 'r', encoding='utf-8') as f:
    content = f.read()

replacements = {
    'bg-[#0A0A0B]': 'bg-[#f8fafc]',
    'bg-[#121215]': 'bg-white',
    'text-slate-200': 'text-slate-800',
    'text-slate-300': 'text-slate-700',
    'text-slate-400': 'text-slate-600',
    'text-white': 'text-slate-900',
    'bg-white/[0.02]': 'bg-white shadow-sm',
    'bg-white/[0.05]': 'bg-slate-50',
    'bg-black/20': 'bg-slate-50',
    'border-white/5': 'border-slate-200',
    'border-white/10': 'border-slate-200',
    'from-white/[0.03]': 'from-white',
    'text-indigo-400': 'text-indigo-600',
    'text-cyan-400': 'text-cyan-600',
    'text-emerald-400': 'text-emerald-600',
    'text-rose-400': 'text-rose-600',
    'text-amber-400': 'text-amber-600',
    'bg-indigo-500/10': 'bg-indigo-100',
    'bg-emerald-500/10': 'bg-emerald-100',
    'bg-rose-500/10': 'bg-rose-100',
    'bg-amber-500/10': 'bg-amber-100',
    'from-indigo-400': 'from-indigo-600',
    'to-cyan-400': 'to-cyan-600',
    'border-indigo-500/30': 'border-indigo-200',
    'border-indigo-500/20': 'border-indigo-200',
    'border-emerald-500/30': 'border-emerald-200',
    'border-emerald-500/20': 'border-emerald-200',
    'border-rose-500/30': 'border-rose-200',
    'border-rose-500/20': 'border-rose-200',
    'border-amber-500/20': 'border-amber-200',
    'bg-white/[0.01]': 'bg-slate-50',
    'bg-indigo-900/10': 'bg-indigo-100',
    'bg-rose-900/10': 'bg-rose-100',
    'text-indigo-300': 'text-indigo-700',
    'text-emerald-300': 'text-emerald-700',
    'stroke=\"#ffffff10\"': 'stroke=\"#e2e8f0\"',
    'stroke=\"#ffffff40\"': 'stroke=\"#94a3b8\"',
    "fill: '#ffffff05'": "fill: '#f1f5f9'",
    "backgroundColor: '#1e1e24', border: '1px solid rgba(255,255,255,0.1)', borderRadius: '12px', color: '#fff'": "backgroundColor: '#ffffff', border: '1px solid #cbd5e1', borderRadius: '12px', color: '#0f172a'",
    'text-white/20': 'text-slate-300',
    'border-cyan-500/30': 'border-cyan-200',
    'bg-white/5': 'bg-white',
    'hover:bg-white/10': 'hover:bg-slate-50',
    'selection:bg-indigo-500/30': 'selection:bg-indigo-500/20'
}

for k, v in replacements.items():
    content = content.replace(k, v)

with open('src/app/page.tsx', 'w', encoding='utf-8') as f:
    f.write(content)
