"use client";
import { Bot, CirclePlus, Files, History, LayoutDashboard, Network, Settings, Globe, Activity } from "lucide-react";

const items = [
  [LayoutDashboard, "Dashboard"], [CirclePlus, "New Task"], [Activity, "Agent Runs"], [Network, "Workflow Builder"],
  [Globe, "Browser Sessions"], [Files, "Generated Files"], [History, "Task History"], [Settings, "Settings"],
] as const;

export function Sidebar() {
  return <aside className="hidden min-h-screen w-64 shrink-0 border-r border-white/10 bg-[#0b0c12] p-5 lg:block">
    <div className="mb-12 flex items-center gap-3"><div className="rounded-xl bg-violet-500/20 p-2 text-violet-300"><Bot size={22} /></div><div><div className="font-semibold tracking-tight">GhostOS</div><div className="text-[10px] uppercase tracking-[.25em] text-slate-500">Operator Core</div></div></div>
    <nav className="space-y-1">{items.map(([Icon, label], index) => <button key={label} className={`flex w-full items-center gap-3 rounded-xl px-3 py-2.5 text-left text-sm ${index === 0 ? "bg-white/10 text-white" : "text-slate-400 hover:bg-white/5 hover:text-white"}`}><Icon size={17} />{label}</button>)}</nav>
    <div className="mt-12 rounded-2xl border border-cyan-400/20 bg-cyan-400/5 p-4"><div className="mb-2 flex items-center gap-2 text-xs text-cyan-200"><span className="h-2 w-2 rounded-full bg-cyan-300" /> System ready</div><p className="text-xs leading-5 text-slate-500">Planning mode only. No automation is active.</p></div>
  </aside>;
}
