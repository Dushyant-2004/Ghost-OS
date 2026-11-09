from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database.session import Base


class ScreenObservation(Base):
    __tablename__ = "screen_observations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    page_url: Mapped[str] = mapped_column(Text)
    page_title: Mapped[str] = mapped_column(Text)
    screenshot_path: Mapped[str] = mapped_column(Text)
    visible_elements: Mapped[list[dict]] = mapped_column(JSON, default=list)
    detected_dialogs: Mapped[list[str]] = mapped_column(JSON, default=list)
    page_state: Mapped[str] = mapped_column(String(40))
    observation_summary: Mapped[str] = mapped_column(Text)
    confidence: Mapped[float] = mapped_column(Float)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
