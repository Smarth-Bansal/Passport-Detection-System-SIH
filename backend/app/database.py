import json
import uuid
from datetime import datetime, timezone
from typing import Generator, Optional, List, Dict, Any

from sqlalchemy import create_engine, Column, String, Float, Boolean, DateTime, Text
from sqlalchemy.orm import sessionmaker, Session, declarative_base

from .config import DATABASE_URL

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    passport_number = Column(String(64), nullable=True, index=True)
    traveler_name = Column(String(128), nullable=True)
    nationality = Column(String(32), nullable=True)
    issuing_country = Column(String(32), nullable=True)
    mrz_checksum_valid = Column(Boolean, default=False)
    tamper_risk_score = Column(Float, default=0.0)
    face_match_score = Column(Float, nullable=True)
    overall_recommendation = Column(String(64), nullable=False)
    model_version = Column(String(64), nullable=False)
    raw_result = Column(Text, nullable=False)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "passport_number": self.passport_number,
            "traveler_name": self.traveler_name,
            "nationality": self.nationality,
            "issuing_country": self.issuing_country,
            "mrz_checksum_valid": self.mrz_checksum_valid,
            "tamper_risk_score": self.tamper_risk_score,
            "face_match_score": self.face_match_score,
            "overall_recommendation": self.overall_recommendation,
            "model_version": self.model_version,
            "details": json.loads(self.raw_result) if self.raw_result else {},
        }


def init_db():
    Base.metadata.create_all(bind=engine)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def save_audit_record(
    db: Session,
    passport_number: Optional[str],
    traveler_name: Optional[str],
    nationality: Optional[str],
    issuing_country: Optional[str],
    mrz_checksum_valid: bool,
    tamper_risk_score: float,
    face_match_score: Optional[float],
    overall_recommendation: str,
    model_version: str,
    raw_result: Dict[str, Any],
) -> AuditLog:
    record = AuditLog(
        id=str(uuid.uuid4()),
        timestamp=datetime.now(timezone.utc),
        passport_number=passport_number,
        traveler_name=traveler_name,
        nationality=nationality,
        issuing_country=issuing_country,
        mrz_checksum_valid=mrz_checksum_valid,
        tamper_risk_score=round(tamper_risk_score, 1),
        face_match_score=round(face_match_score, 1) if face_match_score is not None else None,
        overall_recommendation=overall_recommendation,
        model_version=model_version,
        raw_result=json.dumps(raw_result),
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def get_audit_logs(db: Session, limit: int = 50) -> List[AuditLog]:
    return db.query(AuditLog).order_by(AuditLog.timestamp.desc()).limit(limit).all()


def get_audit_by_id(db: Session, audit_id: str) -> Optional[AuditLog]:
    return db.query(AuditLog).filter(AuditLog.id == audit_id).first()
