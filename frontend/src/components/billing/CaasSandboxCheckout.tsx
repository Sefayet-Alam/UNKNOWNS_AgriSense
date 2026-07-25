"use client";

import { CheckCircle2, Loader2, ReceiptText, X } from "lucide-react";
import { useEffect, useState } from "react";
import { apiCaasDebit, apiCaasQuote } from "@/lib/api";
import type { CaasQuote, CaasReceipt } from "@/lib/types";

export function CaasSandboxCheckout({ onClose, onSuccess }: { onClose: () => void; onSuccess: () => void }) {
  const [quote, setQuote] = useState<CaasQuote | null>(null);
  const [receipt, setReceipt] = useState<CaasReceipt | null>(null);
  const [busy, setBusy] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    apiCaasQuote()
      .then(setQuote)
      .catch((cause) => setError(cause instanceof Error ? cause.message : "Could not load sandbox balance."))
      .finally(() => setBusy(false));
  }, []);

  const pay = async () => {
    setBusy(true);
    setError("");
    try {
      setReceipt(await apiCaasDebit("plus_subscription"));
      onSuccess();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Sandbox debit failed.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center bg-black/40 p-2 sm:items-center sm:p-4">
      <section className="max-h-[calc(100dvh-1rem)] w-full max-w-md overflow-y-auto border border-river-300 bg-surface shadow-2xl">
        <header className="flex items-center justify-between border-b border-river-200 bg-river-50 px-4 py-3">
          <span className="flex items-center gap-2 text-sm font-semibold text-river-950"><ReceiptText size={16} /> BDApps CaaS Sandbox</span>
          <button type="button" onClick={onClose} aria-label="Close" className="p-1 text-text-muted hover:text-text-primary"><X size={18} /></button>
        </header>
        <div className="space-y-4 p-5">
          {!receipt && <p className="text-xs leading-relaxed text-text-muted">BDApps-compatible local simulation. No real mobile balance is charged.</p>}
          {busy && !quote && <div className="flex justify-center py-8"><Loader2 className="animate-spin text-primary-600" /></div>}
          {quote && !receipt && <>
            <dl className="border border-jute-300/70 p-3 text-sm">
              <div className="flex justify-between gap-4 py-1"><dt className="text-text-muted">Plan</dt><dd className="font-medium">{quote.product_name}</dd></div>
              <div className="flex justify-between gap-4 py-1"><dt className="text-text-muted">Sandbox balance</dt><dd className="nums font-semibold">BDT {quote.balance_bdt}</dd></div>
              <div className="flex justify-between gap-4 py-1"><dt className="text-text-muted">Direct debit</dt><dd className="nums font-semibold">BDT {quote.amount_bdt}</dd></div>
            </dl>
            {error && <p className="text-xs text-status-error">{error}</p>}
            <button type="button" disabled={busy} onClick={pay} className="atlas-button w-full disabled:opacity-60">{busy ? <Loader2 size={15} className="animate-spin" /> : null} Confirm sandbox debit</button>
          </>}
          {receipt && <>
            <div className="border border-primary-300 bg-primary-50 p-4 text-sm"><p className="flex items-center gap-2 font-semibold text-primary-900"><CheckCircle2 size={17} /> Receipt: {receipt.status_code}</p><p className="mt-1 text-primary-800">{receipt.status_detail}</p><p className="nums mt-3 font-semibold">BDT {receipt.balance_before_bdt} → BDT {receipt.balance_after_bdt}</p></div>
            <dl className="space-y-1 break-all text-xs text-text-muted"><div>External: {receipt.external_trx_id}</div><div>Internal: {receipt.internal_trx_id}</div><div>Reference: {receipt.reference_id}</div><div>Subscriber: {receipt.request_trace.subscriberId}</div><div>Credential: {receipt.request_trace.password}</div></dl>
            <button type="button" onClick={onClose} className="atlas-button w-full">Close receipt</button>
          </>}
          {error && receipt && <p className="text-xs text-status-error">{error}</p>}
        </div>
      </section>
    </div>
  );
}
