import type { Task } from "../types";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, { ...init, headers: { "Content-Type": "application/json", ...init?.headers } });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(body.detail ?? `Request failed (${response.status})`);
  }
  return response.json() as Promise<T>;
}

export const api = {
  health: () => request<{ status: string; planner_provider: string; planner_configured: boolean }>("/api/health"),
  tasks: () => request<Task[]>("/api/tasks"),
  task: (id: string) => request<Task>(`/api/tasks/${id}`),
  createTask: (instruction: string) => request<Task>("/api/tasks", { method: "POST", body: JSON.stringify({ instruction }) }),
  executeTask: (id: string, approved = false) => request<Task>(`/api/tasks/${id}/execute`, { method: "POST", body: JSON.stringify({ approved }) }),
  artifactUrl: (taskId: string, artifactId: number) => `${API_URL}/api/tasks/${taskId}/artifacts/${artifactId}`,
  events: (id: string, after = 0) => request<TaskEvent[]>(`/api/tasks/${id}/events?after=${after}`),
  approvals: () => request<Approval[]>("/api/approvals"),
  memories: (query = "") => request<Memory[]>(`/api/memories${query ? `?query=${encodeURIComponent(query)}` : ""}`),
  deleteMemory: (id: string) => request<void>(`/api/memories/${id}`, { method: "DELETE" }),
};

export type TaskEvent = { id: number; task_id: string; event_type: string; message: string; timestamp: string };
export type Approval = { id: string; task_id: string; action: string; description: string; status: string; risk_level: string; requested_at: string; };
export type Memory = { memory_id: string; category: string; content: string; importance: number; confidence: number; created_at: string; last_accessed_at: string | null; access_count: number; };
