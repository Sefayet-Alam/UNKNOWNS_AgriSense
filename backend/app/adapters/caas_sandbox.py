"""BDApps CaaS-compatible local simulator; it never calls a carrier gateway."""
from __future__ import annotations

from dataclasses import dataclass
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..models import CaasTransaction, User

OPENING_BALANCE_BDT = 500
PRODUCTS = {
    "plus_subscription": {"name": "AgriSense Plus monthly access", "amount_bdt": 199},
}


@dataclass(frozen=True)
class CaasReceipt:
    transaction: CaasTransaction
    request_trace: dict[str, str]


def subscriber_id(phone: str) -> str:
    return f"tel:88{phone}"


async def current_balance(session: AsyncSession, user_id: int) -> int:
    spent = await session.scalar(
        select(func.coalesce(func.sum(CaasTransaction.amount_bdt), 0)).where(
            CaasTransaction.user_id == user_id,
            CaasTransaction.status_code == "S1000",
        )
    )
    return OPENING_BALANCE_BDT - int(spent or 0)


def build_direct_debit_request(user: User, product_id: str) -> dict[str, str]:
    product = PRODUCTS[product_id]
    app_id = settings.BDAPPS_APPLICATION_ID or "APP_CAAS_SANDBOX"
    account = f"88{user.phone}"
    return {
        "applicationId": app_id,
        "password": "[redacted]",
        "externalTrxId": f"caas-{uuid4().hex}",
        "subscriberId": subscriber_id(user.phone),
        "paymentInstrumentName": "Mobile Account",
        "accountId": account,
        "amount": str(product["amount_bdt"]),
        "currency": "BDT",
    }


async def debit(
    session: AsyncSession, user: User, product_id: str
) -> CaasReceipt:
    if product_id not in PRODUCTS:
        raise ValueError("Unknown CaaS sandbox product.")
    product = PRODUCTS[product_id]
    balance_before = await current_balance(session, user.id)
    amount = int(product["amount_bdt"])
    if balance_before < amount:
        raise ValueError("E1326: Insufficient sandbox operator balance.")

    request_trace = build_direct_debit_request(user, product_id)
    transaction = CaasTransaction(
        user_id=user.id,
        product_id=product_id,
        external_trx_id=request_trace["externalTrxId"],
        internal_trx_id=f"sandbox-{uuid4().hex}",
        reference_id=f"ref-{uuid4().hex[:16]}",
        amount_bdt=amount,
        balance_before_bdt=balance_before,
        balance_after_bdt=balance_before - amount,
        status_code="S1000",
        status_detail="Sandbox direct debit completed.",
    )
    session.add(transaction)
    await session.commit()
    await session.refresh(transaction)
    return CaasReceipt(transaction=transaction, request_trace=request_trace)
