import { WorkspaceShell } from "@/components/workspace/WorkspaceShell";

// Guest mode — use the advisor without signing up. No account, no saved history,
// and no identity is sent to the backend unless the farmer explicitly shares it.
// Runs entirely client-side against the mock agent (STUB, see lib/mockAgent.ts).
export default function GuestPage() {
  return <WorkspaceShell mode="guest" />;
}
