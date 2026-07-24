// bdapps CaaS (Charging-as-a-Service) — SANDBOX SIMULATION (Tier-2, 10-mark feature).
// STUB: responses match the real bdapps CaaS API shapes (dev.bdapps.com) so the flow
// is swappable. In production the browser calls OUR backend, which calls bdapps with
// the applicationId + password (secrets that must NEVER live in the frontend). Success
// status code is "S1000" per the bdapps contract.

const wait = (ms: number) => new Promise((r) => setTimeout(r, ms));
const digits = (n: number) =>
  Array.from({ length: n }, () => Math.floor(Math.random() * 10)).join("");

export interface OtpRequest {
  referenceNo: string;
  otp: string; // demo only — normally delivered by SMS, never returned
  statusCode: string;
  statusDetail: string;
}

export interface VerifyResult {
  ok: boolean;
  statusCode: string;
  statusDetail: string;
}

export interface DebitReceipt {
  externalTrxId: string;
  internalTrxId: string;
  referenceId: string;
  timeStamp: string;
  amount: string;
  currency: string;
  statusCode: string;
  statusDetail: string;
}

export interface BalanceResult {
  accountType: string;
  accountStatus: string;
  chargeableBalance: string;
  statusCode: string;
  statusDetail: string;
}

/** POST /otp/request → referenceNo (we surface the OTP for the demo). */
export async function requestOtp(_mobile: string): Promise<OtpRequest> {
  await wait(700);
  return {
    referenceNo: digits(8),
    otp: digits(6),
    statusCode: "S1000",
    statusDetail: "OTP dispatched.",
  };
}

/** POST /otp/verify → S1000 on match. */
export async function verifyOtp(otp: string, expected: string): Promise<VerifyResult> {
  await wait(600);
  return otp === expected
    ? { ok: true, statusCode: "S1000", statusDetail: "Success." }
    : { ok: false, statusCode: "E1312", statusDetail: "Invalid OTP." };
}

/** POST /caas/get/balance → chargeable balance. */
export async function getBalance(): Promise<BalanceResult> {
  await wait(400);
  return {
    accountType: "Pre Paid",
    accountStatus: "Active",
    chargeableBalance: "850.0",
    statusCode: "S1000",
    statusDetail: "Success.",
  };
}

/** POST /caas/direct/debit → the receipt the demo renders. */
export async function directDebit(amount: number): Promise<DebitReceipt> {
  await wait(900);
  return {
    externalTrxId: digits(20),
    internalTrxId: digits(6),
    referenceId: digits(8),
    timeStamp: new Date().toISOString(),
    amount: String(amount),
    currency: "BDT",
    statusCode: "S1000",
    statusDetail: "Success.",
  };
}
