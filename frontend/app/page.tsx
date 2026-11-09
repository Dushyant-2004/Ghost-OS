import { Dashboard } from "../components/Dashboard";
import { Sidebar } from "../components/Sidebar";

export default function Home() {
  return <div className="flex min-h-screen bg-[radial-gradient(circle_at_80%_0%,#24164c_0%,transparent_32%),#08090d]"><Sidebar /><Dashboard /></div>;
}
