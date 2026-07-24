// Single source of truth for the plan's money math. Pure + deterministic so the
// UI can recompute instantly on any input edit ("change an input → outputs change")
// and so it's unit-testable. All amounts in BDT.

import type { AgriPlan, FinanceLine } from "./plan";

export interface FinanceInputs {
  costs: FinanceLine[];
  yieldKg: number;
  pricePerKg: number;
}

export interface FinanceResult {
  totalCost: number;
  revenue: number;
  netProfit: number;
  roiPct: number; // net / cost * 100
  breakEvenKg: number; // cost / pricePerKg
}

export function computeFinance(input: FinanceInputs): FinanceResult {
  const totalCost = input.costs.reduce((s, c) => s + (Number(c.amount) || 0), 0);
  const yieldKg = Number(input.yieldKg) || 0;
  const price = Number(input.pricePerKg) || 0;
  const revenue = yieldKg * price;
  const netProfit = revenue - totalCost;
  const roiPct = totalCost > 0 ? (netProfit / totalCost) * 100 : 0;
  const breakEvenKg = price > 0 ? totalCost / price : 0;
  return {
    totalCost,
    revenue,
    netProfit,
    roiPct: Math.round(roiPct),
    breakEvenKg: Math.round(breakEvenKg),
  };
}

export function financeOf(plan: AgriPlan): FinanceResult {
  return computeFinance(plan.finance);
}

/** BDT formatter — e.g. 16060 → "৳16,060". */
export function bdt(n: number): string {
  const sign = n < 0 ? "-" : "";
  return `${sign}৳${Math.abs(Math.round(n)).toLocaleString("en-IN")}`;
}
