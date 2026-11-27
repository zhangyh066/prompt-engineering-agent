from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, ForeignKey, JSON, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class RunRecord(Base):
    __tablename__ = "runs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    status: Mapped[str] = mapped_column(String(32), index=True)
    user_request: Mapped[str] = mapped_column(Text)
    raw_prompt: Mapped[str | None] = mapped_column(Text, nullable=True)
    task_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    provider: Mapped[str] = mapped_column(String(32))
    model: Mapped[str] = mapped_column(String(255))
    total_tokens: Mapped[int | None] = mapped_column(nullable=True)
    total_cost_usd: Mapped[Decimal | None] = mapped_column(Numeric(14, 8), nullable=True)
    total_latency_seconds: Mapped[float] = mapped_column(default=0.0)
    optimization_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    adapted_prompt_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    clarification_questions_json: Mapped[list] = mapped_column(JSON, default=list)
    warnings_json: Mapped[list] = mapped_column(JSON, default=list)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    versions: Mapped[list["VersionRecord"]] = relationship(
        back_populates="run",
        cascade="all, delete-orphan",
        order_by="VersionRecord.version_number",
    )


class VersionRecord(Base):
    __tablename__ = "prompt_versions"
    __table_args__ = (UniqueConstraint("run_id", "version_number"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("runs.id"), index=True)
    version_number: Mapped[int] = mapped_column()
    content: Mapped[str] = mapped_column(Text)
    generation_method: Mapped[str] = mapped_column(String(50))
    changes_json: Mapped[list] = mapped_column(JSON)
    strategies_json: Mapped[list] = mapped_column(JSON)
    evaluation_json: Mapped[dict] = mapped_column(JSON)
    is_best: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    run: Mapped[RunRecord] = relationship(back_populates="versions")
