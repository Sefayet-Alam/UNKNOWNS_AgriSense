# BDApps CaaS Sandbox Design

## Goal

Add a truthful, demo-ready one-time BDApps CaaS checkout that shows operator balance before and after debit plus a receipt, without calling the unavailable real carrier gateway.

## Scope

The feature is separate from the existing recurring Plus/Pro subscription checkout. It is a Tier 2 sandbox purchase for a farmer input bundle. It uses the same field names and response shape as BDApps CaaS Direct Debit and is visibly labelled `BDApps CaaS sandbox` in the UI and trace.

## Architecture

- A `CaasSandboxProvider` owns a deterministic operator account ledger. New users receive BDT 500 virtual balance, scoped to their authenticated account.
- `POST /api/billing/caas/quote` returns the product, `subscriberId`, and current virtual balance.
- `POST /api/billing/caas/debit` accepts a product id and an explicit `confirm=true`. It generates a unique external transaction ID, verifies sufficient balance, deducts once, persists a receipt, and returns redacted request data and raw-compatible response data.
- A `CaasTransaction` table provides durable idempotency and receipts. The unique `external_trx_id` prevents duplicate debit if a browser retries a completed request.
- The profile Billing tab presents a compact CaaS Sandbox Checkout for a fixed BDT 50 input bundle, balance before/after, receipt, and a trace drawer. It cannot modify subscription state.

## BDApps Compatibility Contract

The simulator constructs the Direct Debit request shape:

```json
{
  "applicationId": "APP_139278",
  "password": "[redacted]",
  "externalTrxId": "unique application transaction id",
  "subscriberId": "tel:8801...",
  "paymentInstrumentName": "Mobile Account",
  "accountId": "8801...",
  "amount": "50",
  "currency": "BDT"
}
```

The receipt contains `statusCode`, `statusDetail`, `externalTrxId`, `internalTrxId`, `referenceId`, and `timeStamp`. The response must never return an API key.

## Failure Handling

- `confirm=false`: reject without debit.
- Unknown product or amount altered by the client: reject; server owns price.
- Insufficient virtual balance: return a BDApps-style `E1326` response and do not persist a successful receipt.
- Repeated external transaction: return the existing receipt without another deduction.
- The real gateway remains off because complete balance probes on both documented hosts and paths returned HTTP 404. No screen may state that real mobile balance was charged.

## Verification

- Unit tests: request shape, starting balance, successful debit, insufficient balance, idempotency, and secret redaction.
- Integration tests: authenticated quote/debit route and persisted receipt.
- Frontend: typecheck and production build; browser checkout shows the BDT 500 to BDT 450 transition and a receipt.
