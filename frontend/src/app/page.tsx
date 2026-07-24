"use client";

// Root: route by presence of a stored token (authed -> /chat, else -> /login).

import { useRouter } from "next/navigation";
import { useEffect } from "react";
import { getAccess } from "@/lib/tokens";

export default function RootPage() {
  const router = useRouter();

  useEffect(() => {
    router.replace(getAccess() ? "/chat" : "/login");
  }, [router]);

  return (
    <div className="flex h-screen items-center justify-center bg-background text-text-muted">
      Loading…
    </div>
  );
}
