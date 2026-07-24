"use client";

import { ArrowLeft, BadgeCheck } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { LeafMark } from "@/components/ui/LeafMark";
import { PasswordInput } from "@/components/ui/PasswordInput";
import { TextInput } from "@/components/ui/TextInput";
import {
  apiConfirmPasswordReset,
  apiRequestPasswordReset,
} from "@/lib/api";
import { isValidBdPhone } from "@/lib/phone";

type Step = "request" | "verify" | "done";

export default function ForgotPasswordPage() {
  const [step, setStep] = useState<Step>("request");
  const [phone, setPhone] = useState("");
  const [challengeId, setChallengeId] = useState("");
  const [demoOtp, setDemoOtp] = useState<string | null>(null);
  const [otp, setOtp] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const requestCode = async (event: React.FormEvent) => {
    event.preventDefault();
    setError("");
    if (!isValidBdPhone(phone)) {
      setError("Enter a valid Bangladeshi mobile number.");
      return;
    }
    setBusy(true);
    try {
      const result = await apiRequestPasswordReset(phone);
      setChallengeId(result.challenge_id);
      setDemoOtp(result.demo_otp);
      setStep("verify");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not request a code.");
    } finally {
      setBusy(false);
    }
  };

  const resetPassword = async (event: React.FormEvent) => {
    event.preventDefault();
    setError("");
    if (otp.length < 4) return setError("Enter the OTP.");
    if (password.length < 8)
      return setError("Password must be at least 8 characters.");
    if (password !== confirm) return setError("Passwords do not match.");
    setBusy(true);
    try {
      await apiConfirmPasswordReset(challengeId, otp, password);
      setStep("done");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not reset password.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <main className="leaf-vein-bg flex min-h-screen items-center justify-center bg-background px-4 py-10">
      <div className="w-full max-w-md">
        <div className="mb-6 flex justify-center">
          <LeafMark size="lg" />
        </div>
        <div className="rounded-2xl border border-border bg-surface p-7 shadow-card">
          {step === "request" && (
            <>
              <h1 className="font-display text-2xl font-semibold tracking-tight">
                Reset your password
              </h1>
              <p className="mb-6 mt-1 text-sm text-text-muted">
                Enter the mobile number registered with AgriSense.
              </p>
              <form onSubmit={requestCode} className="space-y-4">
                <TextInput
                  label="Mobile number"
                  type="tel"
                  inputMode="numeric"
                  autoComplete="tel"
                  placeholder="01XXXXXXXXX"
                  value={phone}
                  onChange={(event) => setPhone(event.target.value)}
                  autoFocus
                />
                {error && <p className="text-xs text-status-error">{error}</p>}
                <button
                  type="submit"
                  disabled={busy}
                  className="w-full rounded-xl bg-primary-600 px-4 py-2.5 font-medium text-white transition hover:bg-primary-700 disabled:opacity-60"
                >
                  {busy ? "Preparing code…" : "Send reset code"}
                </button>
              </form>
            </>
          )}

          {step === "verify" && (
            <>
              <h1 className="font-display text-2xl font-semibold tracking-tight">
                Choose a new password
              </h1>
              <p className="mb-4 mt-1 text-sm text-text-muted">
                Enter the code for {phone} and set your new password.
              </p>
              {demoOtp && (
                <p className="mb-4 rounded-lg border border-primary-200 bg-primary-50 px-3 py-2 font-mono text-xs text-primary-800">
                  Demo OTP:{" "}
                  <span className="font-semibold tracking-widest">{demoOtp}</span>
                </p>
              )}
              <form onSubmit={resetPassword} className="space-y-4">
                <TextInput
                  label="Reset code"
                  inputMode="numeric"
                  maxLength={8}
                  value={otp}
                  onChange={(event) =>
                    setOtp(event.target.value.replace(/\D/g, ""))
                  }
                  autoFocus
                />
                <PasswordInput
                  label="New password"
                  value={password}
                  onChange={(event) => setPassword(event.target.value)}
                  autoComplete="new-password"
                />
                <PasswordInput
                  label="Confirm new password"
                  value={confirm}
                  onChange={(event) => setConfirm(event.target.value)}
                  autoComplete="new-password"
                />
                {error && <p className="text-xs text-status-error">{error}</p>}
                <button
                  type="submit"
                  disabled={busy}
                  className="w-full rounded-xl bg-primary-600 px-4 py-2.5 font-medium text-white transition hover:bg-primary-700 disabled:opacity-60"
                >
                  {busy ? "Resetting…" : "Reset password"}
                </button>
              </form>
            </>
          )}

          {step === "done" && (
            <div className="py-4 text-center">
              <span className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-primary-100 text-primary-700">
                <BadgeCheck size={24} />
              </span>
              <h1 className="mt-3 font-display text-xl font-semibold">
                Password updated
              </h1>
              <p className="mt-1 text-sm text-text-muted">
                You can now sign in with your new password.
              </p>
              <Link
                href="/login"
                className="mt-5 inline-flex rounded-xl bg-primary-600 px-5 py-2.5 text-sm font-medium text-white hover:bg-primary-700"
              >
                Go to sign in
              </Link>
            </div>
          )}

          {step !== "done" && (
            <Link
              href="/login"
              className="mt-6 flex items-center justify-center gap-1 text-xs font-medium text-text-muted hover:text-primary-700"
            >
              <ArrowLeft size={13} /> Back to sign in
            </Link>
          )}
        </div>
      </div>
    </main>
  );
}
