"use client";

// bdapps CaaS checkout modal: mobile → OTP → direct debit → receipt. Renders the
// operator balance deduction and the S1000 receipt (the scored demo flow). Simulated
// via lib/bdapps.ts — see that file for the real-vs-mock note.

import { BadgeCheck, Check, Loader2, ShieldCheck, Smartphone, X } from "lucide-react";
import { useState } from "react";
import {
  type DebitReceipt,
  directDebit,
  getBalance,
  requestOtp,
  verifyOtp,
} from "@/lib/bdapps";
import { formatBdPhone } from "@/lib/phone";

type Step = "confirm" | "otp" | "processing" | "receipt";

interface Props {
  tierName: string;
  amount: number;
  mobile: string;
  onClose: () => void;
  onSuccess: () => void;
}

const row = "flex justify-between gap-4 py-1";

export function BdAppsCheckout({ tierName, amount, mobile, onClose, onSuccess }: Props) {
  const [step, setStep] = useState<Step>("confirm");
  const [busy, setBusy] = useState(false);
  const [otpRef, setOtpRef] = useState("");
  const [expectedOtp, setExpectedOtp] = useState("");
  const [otp, setOtp] = useState("");
  const [err, setErr] = useState("");
  const [balBefore, setBalBefore] = useState("0");
  const [receipt, setReceipt] = useState<DebitReceipt | null>(null);

  const balAfter = (parseFloat(balBefore) - amount).toFixed(1);

  const sendOtp = async () => {
    setBusy(true);
    setErr("");
    const [r, b] = await Promise.all([requestOtp(mobile), getBalance()]);
    setOtpRef(r.referenceNo);
    setExpectedOtp(r.otp);
    setBalBefore(b.chargeableBalance);
    setStep("otp");
    setBusy(false);
  };

  const confirmPay = async () => {
    setBusy(true);
    setErr("");
    const v = await verifyOtp(otp, expectedOtp);
    if (!v.ok) {
      setErr(`${v.statusDetail} (${v.statusCode})`);
      setBusy(false);
      return;
    }
    setStep("processing");
    const rec = await directDebit(amount);
    setReceipt(rec);
    setStep("receipt");
    setBusy(false);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div className="w-full max-w-sm overflow-hidden rounded-2xl border border-border bg-surface shadow-xl">
        <div className="flex items-center justify-between border-b border-border bg-surface-muted px-4 py-3">
          <span className="flex items-center gap-2 text-sm font-semibold text-text-primary">
            <ShieldCheck size={16} className="text-primary-600" /> Pay with bdapps
          </span>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close"
            className="text-text-muted transition hover:text-text-primary"
          >
            <X size={18} />
          </button>
        </div>

        <div className="p-5">
          {step === "confirm" && (
            <div className="space-y-4">
              <div className="rounded-xl border border-border p-3 text-sm">
                <div className={row}>
                  <span className="text-text-muted">Plan</span>
                  <span className="font-medium text-text-primary">AgriSense {tierName}</span>
                </div>
                <div className={row}>
                  <span className="text-text-muted">Amount</span>
                  <span className="nums font-semibold text-text-primary">৳{amount} BDT</span>
                </div>
                <div className={row}>
                  <span className="text-text-muted">Charge to</span>
                  <span className="nums font-medium text-text-primary">{formatBdPhone(mobile)}</span>
                </div>
              </div>
              <p className="text-xs text-text-muted">
                We&apos;ll send a one-time code to your mobile, then deduct the amount from your
                operator balance via bdapps CaaS.
              </p>
              <button
                type="button"
                onClick={sendOtp}
                disabled={busy}
                className="flex w-full items-center justify-center gap-2 rounded-xl bg-primary-600 py-2.5 text-sm font-medium text-white transition hover:bg-primary-700 disabled:opacity-60"
              >
                {busy ? <Loader2 size={15} className="animate-spin" /> : <Smartphone size={15} />}
                Send OTP
              </button>
            </div>
          )}

          {step === "otp" && (
            <div className="space-y-4">
              <p className="text-sm text-text-primary">
                Enter the code sent to {formatBdPhone(mobile)}.
              </p>
              <p className="rounded-lg border border-primary-200 bg-primary-50 px-3 py-2 font-mono text-xs text-primary-800">
                Demo OTP: <span className="nums font-semibold tracking-widest">{expectedOtp}</span>{" "}
                <span className="text-primary-700">(normally sent by SMS)</span>
              </p>
              <input
                inputMode="numeric"
                maxLength={6}
                value={otp}
                onChange={(e) => setOtp(e.target.value.replace(/\D/g, ""))}
                placeholder="6-digit code"
                className="nums w-full rounded-xl border border-border bg-surface px-3.5 py-2.5 text-center font-mono text-lg tracking-[0.4em] outline-none focus:border-primary-400"
              />
              {err && <p className="text-xs text-status-error">{err}</p>}
              <button
                type="button"
                onClick={confirmPay}
                disabled={busy || otp.length !== 6}
                className="flex w-full items-center justify-center gap-2 rounded-xl bg-primary-600 py-2.5 text-sm font-medium text-white transition hover:bg-primary-700 disabled:opacity-60"
              >
                {busy ? <Loader2 size={15} className="animate-spin" /> : null}
                Confirm & pay ৳{amount}
              </button>
            </div>
          )}

          {step === "processing" && (
            <div className="flex flex-col items-center gap-3 py-8 text-center">
              <Loader2 size={28} className="animate-spin text-primary-600" />
              <p className="text-sm text-text-muted">Charging your mobile balance…</p>
            </div>
          )}

          {step === "receipt" && receipt && (
            <div className="space-y-4">
              <div className="flex flex-col items-center gap-1 text-center">
                <span className="flex h-12 w-12 items-center justify-center rounded-full bg-primary-100 text-primary-600">
                  <Check size={26} />
                </span>
                <p className="font-display text-lg font-semibold text-text-primary">Payment successful</p>
                <p className="text-xs text-text-muted">
                  {receipt.statusDetail} ({receipt.statusCode})
                </p>
              </div>
              <div className="rounded-xl border border-border p-3 font-mono text-xs">
                <div className={row}>
                  <span className="text-text-muted">Amount</span>
                  <span className="nums text-text-primary">৳{receipt.amount} {receipt.currency}</span>
                </div>
                <div className={row}>
                  <span className="text-text-muted">Balance</span>
                  <span className="nums text-text-primary">
                    ৳{balBefore} → ৳{balAfter}
                  </span>
                </div>
                <div className={row}>
                  <span className="text-text-muted">internalTrxId</span>
                  <span className="nums text-text-primary">{receipt.internalTrxId}</span>
                </div>
                <div className={row}>
                  <span className="text-text-muted">referenceId</span>
                  <span className="nums text-text-primary">{receipt.referenceId}</span>
                </div>
                <div className="flex flex-col border-t border-border pt-1">
                  <span className="text-text-muted">externalTrxId</span>
                  <span className="nums break-all text-text-primary">{receipt.externalTrxId}</span>
                </div>
              </div>
              <button
                type="button"
                onClick={onSuccess}
                className="flex w-full items-center justify-center gap-2 rounded-xl bg-primary-600 py-2.5 text-sm font-medium text-white transition hover:bg-primary-700"
              >
                <BadgeCheck size={15} /> Activate {tierName}
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
