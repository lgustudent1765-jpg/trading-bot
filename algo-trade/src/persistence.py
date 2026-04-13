# file: src/persistence.py
"""
SQLAlchemy-based persistence for open positions and recent signals.
Supports SQLite (local) and PostgreSQL (Railway).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional, List

from sqlalchemy import create_engine, Column, String, Float, Integer, DateTime, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session

from src.logger import get_logger
from src.config import get_config

log = get_logger(__name__)

Base = declarative_base()

class PositionRecord(Base):
    __tablename__ = "positions"

    option_symbol = Column(String, primary_key=True)
    symbol = Column(String, nullable=False)
    direction = Column(String, nullable=False)
    entry_price = Column(Float, nullable=False)
    stop_loss = Column(Float, nullable=False)
    take_profit = Column(Float, nullable=False)
    quantity = Column(Integer, nullable=False)
    underlying_price = Column(Float, default=0.0)
    opened_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

class CooldownRecord(Base):
    __tablename__ = "cooldowns"

    symbol = Column(String, primary_key=True)
    last_signal_at = Column(DateTime, nullable=False)


class SignalRecord(Base):
    __tablename__ = "signals"

    id = Column(Integer, primary_key=True, autoincrement=True)
    symbol = Column(String, nullable=False)
    direction = Column(String, nullable=False)
    strike = Column(Float)
    expiry = Column(String)
    entry = Column(Float)
    stop = Column(Float)
    target = Column(Float)
    size = Column(Integer)
    rationale = Column(String)
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class PositionStore:
    """
    Thread-safe (single asyncio event loop) position and cooldown store.
    Backed by SQLAlchemy (PostgreSQL or SQLite).
    """

    def __init__(self) -> None:
        cfg = get_config()
        db_url = cfg.get("database", {}).get("url", "sqlite:///data/algo_trade.db")
        
        # Handle the case where the data directory might not exist for SQLite
        if db_url.startswith("sqlite:///data/"):
            from pathlib import Path
            Path("data").mkdir(exist_ok=True)

        self.engine = create_engine(db_url, pool_pre_ping=True)
        Base.metadata.create_all(self.engine)
        self.SessionLocal = sessionmaker(bind=self.engine)
        
        log.info("database persistence initialised", url=db_url.split("@")[-1] if "@" in db_url else db_url)

    # ------------------------------------------------------------------ #
    # Positions                                                            #
    # ------------------------------------------------------------------ #

    def add_position(
        self,
        option_symbol: str,
        symbol: str,
        direction: str,
        entry_price: float,
        stop_loss: float,
        take_profit: float,
        quantity: int,
        underlying_price: float = 0.0,
    ) -> None:
        with self.SessionLocal() as session:
            pos = PositionRecord(
                option_symbol=option_symbol,
                symbol=symbol,
                direction=direction,
                entry_price=entry_price,
                stop_loss=stop_loss,
                take_profit=take_profit,
                quantity=quantity,
                underlying_price=underlying_price,
                opened_at=datetime.now(timezone.utc)
            )
            session.merge(pos) # merge handles update if already exists
            session.commit()
        log.info("position saved to db", option_symbol=option_symbol)

    def remove_position(self, option_symbol: str) -> None:
        with self.SessionLocal() as session:
            pos = session.query(PositionRecord).filter_by(option_symbol=option_symbol).first()
            if pos:
                session.delete(pos)
                session.commit()
                log.info("position removed from db", option_symbol=option_symbol)

    def get_positions(self) -> Dict[str, Dict[str, Any]]:
        with self.SessionLocal() as session:
            records = session.query(PositionRecord).all()
            return {
                r.option_symbol: {
                    "symbol": r.symbol,
                    "option_symbol": r.option_symbol,
                    "direction": r.direction,
                    "entry_price": r.entry_price,
                    "stop_loss": r.stop_loss,
                    "take_profit": r.take_profit,
                    "quantity": r.quantity,
                    "underlying_price": r.underlying_price,
                    "opened_at": r.opened_at.isoformat() if r.opened_at else None,
                }
                for r in records
            }

    @property
    def open_count(self) -> int:
        with self.SessionLocal() as session:
            return session.query(PositionRecord).count()

    def symbols(self) -> list:
        with self.SessionLocal() as session:
            return [r.symbol for r in session.query(PositionRecord.symbol).all()]

    # ------------------------------------------------------------------ #
    # Signals                                                              #
    # ------------------------------------------------------------------ #

    def add_signal(self, data: Dict[str, Any]) -> None:
        with self.SessionLocal() as session:
            sig = SignalRecord(
                symbol=data.get("symbol"),
                direction=data.get("direction"),
                strike=data.get("strike"),
                expiry=data.get("expiry"),
                entry=data.get("entry"),
                stop=data.get("stop"),
                target=data.get("target"),
                size=data.get("size"),
                rationale=data.get("rationale"),
                timestamp=datetime.fromisoformat(data["ts"]) if "ts" in data else datetime.now(timezone.utc)
            )
            session.add(sig)
            session.commit()

    def get_signals(self, limit: int = 100) -> List[Dict[str, Any]]:
        with self.SessionLocal() as session:
            records = session.query(SignalRecord).order_by(SignalRecord.timestamp.desc()).limit(limit).all()
            return [
                {
                    "symbol": r.symbol,
                    "direction": r.direction,
                    "strike": r.strike,
                    "expiry": r.expiry,
                    "entry": r.entry,
                    "stop": r.stop,
                    "target": r.target,
                    "size": r.size,
                    "rationale": r.rationale,
                    "ts": r.timestamp.isoformat() if r.timestamp else None,
                }
                for r in reversed(records) # return in chronological order
            ]

    # ------------------------------------------------------------------ #
    # Signal cooldowns                                                     #
    # ------------------------------------------------------------------ #

    def set_cooldown(self, symbol: str) -> None:
        """Record that a signal was just emitted for *symbol*."""
        with self.SessionLocal() as session:
            cooldown = CooldownRecord(
                symbol=symbol,
                last_signal_at=datetime.now(timezone.utc)
            )
            session.merge(cooldown)
            session.commit()

    def is_on_cooldown(self, symbol: str, cooldown_minutes: int = 30) -> bool:
        """Return True if *symbol* had a signal within *cooldown_minutes*."""
        with self.SessionLocal() as session:
            record = session.query(CooldownRecord).filter_by(symbol=symbol).first()
            if not record:
                return False
            
            # Ensure record.last_signal_at is timezone-aware if it comes from DB without it
            last = record.last_signal_at
            if last.tzinfo is None:
                last = last.replace(tzinfo=timezone.utc)
                
            elapsed = (datetime.now(timezone.utc) - last).total_seconds()
            return elapsed < cooldown_minutes * 60
