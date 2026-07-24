"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { isValidBdPhone } from "@/lib/phone";
import { getAccess } from "@/lib/tokens";
import { AuthShell } from "@/components/layout/AuthShell";
import { PasswordInput } from "@/components/ui/PasswordInput";
import { TextInput } from "@/components/ui/TextInput";

export default function LoginPage() {
  const router = useRouter();
  const { login } = useAuth();

  const [phone, setPhone] = useState("");
  const [password, setPassword] = useState("");
  const [touched, setTouched] = useState<{ u?: boolean; p?: boolean }>({});
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  // Already authed -> skip to chat.
  useEffect(() => {
    if (getAccess()) router.replace("/chat");
  }, [router]);

  const phoneError =
    touched.u && !isValidBdPhone(phone)
      ? "Enter a valid mobile number (e.g. 01712345678)."
      : undefined;
  const passError =
    touched.p && !password ? "Password is required." : undefined;

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setTouched({ u: true, p: true });
    setFormError(null);
    if (!isValidBdPhone(phone) || !password) return;

    setSubmitting(true);
    try {
      await login(phone.trim(), password);
      router.replace("/chat");
    } catch (err) {
      setFormError(
        err instanceof ApiError && err.status === 401
          ? "Invalid mobile number or password."
          : "Could not sign in. Please try again.",
      );
      setSubmitting(false);
    }
  };

  return (
    <AuthShell
      eyebrow="Return to the field ledger"
      title="Welcome back."
      description="Open the seasons, conversations, and crop decisions already waiting in your workspace."
      aside={<>A useful plan remembers what the last rain changed.</>}
    >
      <form onSubmit={onSubmit} className="flex flex-col gap-4" noValidate>
            <TextInput
              label="Mobile number"
              type="tel"
              inputMode="numeric"
              value={phone}
              onChange={(e) => setPhone(e.target.value)}
              onBlur={() => setTouched((t) => ({ ...t, u: true }))}
              error={phoneError}
              autoComplete="tel"
              placeholder="01XXXXXXXXX"
              autoFocus
            />
            <PasswordInput
              label="Password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              onBlur={() => setTouched((t) => ({ ...t, p: true }))}
              error={passError}
              autoComplete="current-password"
            />
            <div className="-mt-1 text-right">
              <Link
                href="/forgot-password"
                className="text-xs font-semibold text-field-700 underline decoration-jute-300 underline-offset-4 transition hover:text-clay-500"
              >
                Forgot password?
              </Link>
            </div>

            {formError && (
              <div className="border border-status-error bg-status-error-chip px-3 py-2 text-sm text-status-error">
                {formError}
              </div>
            )}

            <button
              type="submit"
              disabled={submitting}
              className="atlas-button mt-1 w-full disabled:cursor-not-allowed disabled:opacity-70"
            >
              {submitting ? "Signing in…" : "Sign in"}
            </button>
      </form>

          <p className="mt-6 text-sm text-text-muted">
            New to AgriSense?{" "}
            <Link
              href="/register"
              className="font-semibold text-field-700 transition hover:text-clay-500"
            >
              Create an account
            </Link>
          </p>
    </AuthShell>
  );
}
