import { WorkspaceShell } from "@/components/workspace/WorkspaceShell";

// M1 thin slice — the workspace running against the mock agent, no backend/auth
// required. Open http://localhost:3000/demo. STUB: mock agent (see lib/mockAgent.ts).
export default function DemoPage() {
  return <WorkspaceShell />;
}
