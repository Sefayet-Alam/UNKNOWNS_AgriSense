"use client";

import { ArrowLeft, BadgeCheck } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { AuthShell } from "@/components/layout/AuthShell";
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
    <AuthShell
      eyebrow="Account recovery"
      title={step === "done" ? "Your key is renewed." : "Return to your field notes."}
      description="Verify the mobile number attached to your AgriSense account, then choose a new password."
      aside={<>A lost password should not mean a lost season.</>}
    >
          {step === "request" && (
            <>
              <h2 className="font-display text-2xl tracking-[-0.03em]">
                Request a reset code
              </h2>
              <p className="mb-6 mt-2 text-sm text-text-muted">
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
                  className="atlas-button w-full disabled:opacity-60"
                >
                  {busy ? "Preparing code…" : "Send reset code"}
                </button>
              </form>
            </>
          )}

          {step === "verify" && (
            <>
              <h2 className="font-display text-2xl tracking-[-0.03em]">
                Choose a new password
              </h2>
              <p className="mb-4 mt-1 text-sm text-text-muted">
                Enter the code for {phone} and set your new password.
              </p>
              {demoOtp && (
                <p className="mb-4 border border-jute-300 bg-jute-100 px-3 py-2 font-mono text-xs text-field-900">
                  Development OTP:{" "}
                  <span className="font-semibold tracking-widest">{demoOtp || "1234"}</span>
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
                  className="atlas-button w-full disabled:opacity-60"
                >
                  {busy ? "Resetting…" : "Reset password"}
                </button>
              </form>
            </>
          )}

          {step === "done" && (
            <div className="py-4 text-center">
              <span className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-field-100 text-field-700">
                <BadgeCheck size={24} />
              </span>
              <h2 className="mt-3 font-display text-2xl">
                Password updated
              </h2>
              <p className="mt-1 text-sm text-text-muted">
                You can now sign in with your new password.
              </p>
              <Link
                href="/login"
                className="atlas-button mt-5"
              >
                Go to sign in
              </Link>
            </div>
          )}

          {step !== "done" && (
            <Link
              href="/login"
              className="mt-6 flex items-center gap-1 text-xs font-semibold text-text-muted transition hover:-translate-x-0.5 hover:text-field-700"
            >
              <ArrowLeft size={13} /> Back to sign in
            </Link>
          )}
    </AuthShell>
  );
}
