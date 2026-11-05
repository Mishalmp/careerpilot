import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, ForeignKey, Numeric, Text, UniqueConstraint, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from careerpilot.core.db import Base


class FxRate(Base):
    """An exchange rate you entered: how many rupees one unit of a currency is worth, and when."""

    __tablename__ = "fx_rates"
    __table_args__ = (UniqueConstraint("owner_id", "currency", name="uq_fx_rates_owner_currency"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    currency: Mapped[str] = mapped_column(Text)
    to_inr: Mapped[Decimal] = mapped_column(Numeric(14, 6))
    as_of: Mapped[date] = mapped_column(Date)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
