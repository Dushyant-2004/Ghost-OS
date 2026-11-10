"use client";
import { FormEvent, useEffect, useState } from "react";
import { ArrowUpRight, CheckCircle2, Clock3, Loader2, Play, Sparkles, XCircle } from "lucide-react";
import { api } from "../lib/api";
import type { Task } from "../types";
import type { Memory } from "../lib/api";

function StatusIcon({ status }: { status: string }) {
  if (status === "completed") return <CheckCircle2 className="text-emerald-400" size={16} />;
  if (status === "running") return <Loader2 className="animate-spin text-cyan-300" size={16} />;
  if (status === "failed") return <XCircle className="text-rose-400" size={16} />;
  return <Clock3 className="text-slate-500" size={16} />;
}

export function Dashboard() {
  const [instruction, setInstruction] = useState("");
  const [tasks, setTasks] = useState<Task[]>([]);
  const [selected, setSelected] = useState<Task | null>(null);
  const [connected, setConnected] = useState<boolean | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [liveEvents, setLiveEvents] = useState<{ event_type: string; message: string }[]>([]);
  const [memories, setMemories] = useState<Memory[]>([]);
  const [analytics, setAnalytics] = useState<{ total_tasks: number; completed_tasks: number; failed_tasks: number; success_rate: number | null } | null>(null);

  useEffect(() => { api.health().then(() => setConnected(true)).catch(() => setConnected(false)); api.tasks().then(setTasks).catch(() => undefined); api.memories().then(setMemories).catch(() => undefined); api.analytics().then(setAnalytics).catch(() => undefined); }, []);
  async function submit(event: FormEvent) {
    event.preventDefault(); if (!instruction.trim()) return;
    setBusy(true); setError("");
    try { const task = await api.createTask(instruction.trim()); setTasks((current) => [task, ...current]); setSelected(task); setInstruction(""); }
    catch (caught) { setError(caught instanceof Error ? caught.message : "Unable to create task"); }
    finally { setBusy(false); }
  }
  async function executeSelected() {
    if (!selected) return;
    setBusy(true); setError("");
    try { const task = await api.executeTask(selected.id, true); setSelected(task); setTasks((current) => current.map((item) => item.id === task.id ? task : item)); }
    catch (caught) { setError(caught instanceof Error ? caught.message : "Unable to execute task"); }
    finally { setBusy(false); }
  }
  useEffect(() => {
    const taskId = selected?.id;
    if (!taskId) return;
    let active = true;
    const poll = async () => {
      try {
        const events = await api.events(taskId);
        if (active) setLiveEvents(events);
      } catch {
        // The task detail remains available when event polling is unavailable.
      }
    };
    void poll();
    const timer = window.setInterval(poll, 1500);
    return () => { active = false; window.clearInterval(timer); };
  }, [selected?.id]);
  return <main className="min-w-0 flex-1 p-5 sm:p-8">
    <header className="mb-9 flex items-start justify-between"><div><p className="mb-2 text-xs uppercase tracking-[.3em] text-violet-300">Mission control</p><h1 className="text-3xl font-semibold tracking-tight sm:text-4xl">Good evening, operator.</h1><p className="mt-2 text-sm text-slate-400">Translate intent into a clear, reviewable execution plan.</p></div><div className="flex items-center gap-2 rounded-full border border-white/10 px-3 py-2 text-xs text-slate-400"><span className={`h-2 w-2 rounded-full ${connected ? "bg-emerald-400" : connected === false ? "bg-rose-400" : "bg-amber-300"}`} />{connected ? "API connected" : connected === false ? "API offline" : "Connecting"}</div></header>
    <form onSubmit={submit} className="glass relative overflow-hidden rounded-3xl p-5 shadow-2xl shadow-violet-950/20"><div className="absolute -right-20 -top-20 h-48 w-48 rounded-full bg-violet-500/10 blur-3xl" /><div className="relative"><div className="mb-4 flex items-center gap-2 text-sm text-slate-300"><Sparkles size={16} className="text-violet-300" /> What should GhostOS plan?</div><textarea value={instruction} onChange={(e) => setInstruction(e.target.value)} placeholder="Describe an outcome, research task, or workflow..." className="min-h-28 w-full resize-none bg-transparent text-lg text-white outline-none placeholder:text-slate-600" /><div className="flex flex-col justify-between gap-4 border-t border-white/10 pt-4 sm:flex-row sm:items-center"><div className="flex flex-wrap gap-2">{["Research a market", "Prepare a project brief", "Compare options"].map((item) => <button type="button" key={item} onClick={() => setInstruction(item)} className="rounded-full border border-white/10 px-3 py-1.5 text-xs text-slate-400 hover:border-violet-400/40 hover:text-white">{item}</button>)}</div><button disabled={busy || !instruction.trim()} className="flex items-center justify-center gap-2 rounded-xl bg-violet-500 px-5 py-2.5 text-sm font-medium text-white transition hover:bg-violet-400 disabled:cursor-not-allowed disabled:opacity-40">{busy ? <Loader2 className="animate-spin" size={16} /> : <Play size={16} />}{busy ? "Planning..." : "Create plan"}</button></div>{error && <p className="mt-3 text-sm text-rose-300">{error}</p>}</div></form>
    <div className="mt-8 grid gap-5 xl:grid-cols-[1.4fr_1fr]"><section className="glass rounded-3xl p-5"><div className="mb-5 flex items-center justify-between"><h2 className="font-medium">Recent tasks</h2><span className="text-xs text-slate-500">{tasks.length} total</span></div>{tasks.length === 0 ? <div className="py-12 text-center text-sm text-slate-500">No tasks yet. Your plans will appear here.</div> : <div className="space-y-2">{tasks.slice(0, 5).map((task) => <button onClick={() => api.task(task.id).then(setSelected).catch(() => undefined)} key={task.id} className="flex w-full items-center justify-between rounded-2xl border border-white/5 bg-white/[.02] p-3 text-left hover:bg-white/[.06]"><div className="min-w-0"><p className="truncate text-sm text-slate-200">{task.title}</p><p className="mt-1 text-xs text-slate-500">{new Date(task.created_at).toLocaleString()}</p></div><div className="ml-3 flex items-center gap-2 text-xs capitalize text-slate-400"><StatusIcon status={task.status} />{task.status}<ArrowUpRight size={14} /></div></button>)}</div>}</section><section className="glass rounded-3xl p-5"><h2 className="mb-5 font-medium">Agent activity</h2><div className="space-y-4">{["Planner Agent", "Research Agent", "Browser Agent", "Coding Agent", "Verification Agent"].map((agent, index) => <div key={agent} className="flex items-center justify-between"><div className="flex items-center gap-3"><div className="h-2 w-2 rounded-full bg-slate-600" /><span className="text-sm text-slate-300">{agent}</span></div><span className="text-xs text-slate-600">{index === 0 ? "Ready" : "Standby"}</span></div>)}</div></section></div>
    {selected?.plan && <section className="glass mt-5 rounded-3xl p-5"><div className="mb-5 flex flex-wrap items-start justify-between gap-3"><div><p className="text-xs uppercase tracking-[.2em] text-cyan-300">Generated plan · {selected.plan.provider} mode</p><h2 className="mt-2 text-xl font-medium">{selected.plan.objective}</h2></div><div className="flex items-center gap-3"><span className="rounded-full border border-amber-300/20 bg-amber-300/5 px-3 py-1 text-xs text-amber-200">Human review required</span><button onClick={executeSelected} disabled={busy || selected.status === "completed"} className="rounded-xl bg-cyan-400 px-4 py-2 text-xs font-semibold text-slate-950 disabled:opacity-40">{busy ? "Running..." : "Approve & run"}</button></div></div><div className="space-y-3">{selected.plan.steps.map((step, index) => <div key={step.step_id} className="flex gap-4 rounded-2xl border border-white/5 p-4"><div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-violet-500/15 text-xs text-violet-200">{index + 1}</div><div><p className="text-sm font-medium text-slate-200">{step.title}</p><p className="mt-1 text-sm leading-6 text-slate-500">{step.description}</p><p className="mt-2 text-xs text-cyan-300/70">Tool: {step.tool_name} · Expected: {step.expected_result}</p></div></div>)}</div></section>}
    {selected?.research_records && selected.research_records.length > 0 && <section className="glass mt-5 rounded-3xl p-5"><h2 className="mb-4 font-medium">Research evidence</h2><div className="space-y-4">{selected.research_records.map((record) => <article key={record.id} className="rounded-2xl border border-white/5 p-4"><div className="flex items-center justify-between gap-3"><a className="text-sm text-cyan-300 hover:underline" href={record.source_url} target="_blank" rel="noreferrer">{record.source_title || record.source_url}</a><span className="text-xs text-slate-500">{record.status} · {record.verification_status}</span></div><p className="mt-2 text-sm text-slate-400">{record.key_findings.join(" ") || record.error_message}</p></article>)}</div>{selected.artifacts && <div className="mt-5 flex flex-wrap gap-3">{selected.artifacts.map((artifact) => <a key={artifact.id} className="rounded-xl bg-cyan-400 px-3 py-2 text-xs font-semibold text-slate-950" href={api.artifactUrl(selected.id, artifact.id)} download>{artifact.filename}</a>)}</div>}</section>}
    {selected && <section className="glass mt-5 rounded-3xl p-5"><div className="mb-4 flex items-center justify-between"><h2 className="font-medium">Live execution timeline</h2><span className="text-xs text-slate-500">{selected.research_status ?? selected.status}</span></div><div className="space-y-2">{liveEvents.slice(-8).map((event, index) => <div key={`${event.event_type}-${index}`} className="rounded-xl border border-white/5 px-3 py-2"><p className="text-xs text-cyan-300">{event.event_type}</p><p className="text-sm text-slate-400">{event.message}</p></div>)}</div></section>}
    <section className="glass mt-5 rounded-3xl p-5"><div className="mb-4 flex items-center justify-between"><h2 className="font-medium">Memory Center</h2><span className="text-xs text-slate-500">{memories.length} saved</span></div>{memories.length === 0 ? <p className="text-sm text-slate-500">No persistent context saved.</p> : <div className="space-y-2">{memories.slice(0, 5).map((memory) => <div key={memory.memory_id} className="flex items-start justify-between gap-3 rounded-xl border border-white/5 px-3 py-2"><div><p className="text-xs uppercase tracking-wide text-violet-300">{memory.category}</p><p className="text-sm text-slate-400">{memory.content}</p></div><button onClick={() => api.deleteMemory(memory.memory_id).then(() => setMemories((items) => items.filter((item) => item.memory_id !== memory.memory_id)))} className="text-xs text-rose-300 hover:text-rose-200">Delete</button></div>)}</div>}</section>
    {analytics && <section className="glass mt-5 rounded-3xl p-5"><h2 className="mb-4 font-medium">Agent analytics</h2><div className="grid grid-cols-2 gap-3 text-sm sm:grid-cols-4"><div><p className="text-xs text-slate-500">Tasks</p><p className="mt-1 text-xl text-white">{analytics.total_tasks}</p></div><div><p className="text-xs text-slate-500">Completed</p><p className="mt-1 text-xl text-emerald-300">{analytics.completed_tasks}</p></div><div><p className="text-xs text-slate-500">Failed</p><p className="mt-1 text-xl text-rose-300">{analytics.failed_tasks}</p></div><div><p className="text-xs text-slate-500">Success rate</p><p className="mt-1 text-xl text-cyan-300">{analytics.success_rate === null ? "N/A" : `${Math.round(analytics.success_rate * 100)}%`}</p></div></div></section>}
  </main>;
}
