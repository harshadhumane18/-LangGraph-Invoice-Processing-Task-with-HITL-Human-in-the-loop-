"""
Database models and utilities for checkpoint persistence
"""
from sqlalchemy import create_engine, Column, String, Float, DateTime, Text, JSON, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime
import json
from src.config import settings

# Database setup
engine = create_engine(settings.DATABASE_URL, connect_args={"check_same_thread": False} if "sqlite" in settings.DATABASE_URL else {})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class CheckpointModel(Base):
    """Model for storing workflow checkpoints"""
    __tablename__ = settings.CHECKPOINT_TABLE
    
    checkpoint_id = Column(String, primary_key=True, index=True)
    workflow_id = Column(String, index=True)
    invoice_id = Column(String, index=True)
    vendor_name = Column(String)
    amount = Column(Float)
    currency = Column(String)
    state_blob = Column(JSON)
    created_at = Column(DateTime, default=datetime.utcnow)
    reason_for_hold = Column(String)
    review_url = Column(String)
    status = Column(String, default="PENDING")
    reviewer_id = Column(String, nullable=True)
    decision = Column(String, nullable=True)
    decision_notes = Column(String, nullable=True)
    decided_at = Column(DateTime, nullable=True)


class HumanReviewQueueModel(Base):
    """Model for human review queue"""
    __tablename__ = settings.HUMAN_REVIEW_QUEUE_TABLE
    
    id = Column(String, primary_key=True, index=True)
    checkpoint_id = Column(String, index=True)
    invoice_id = Column(String, index=True)
    vendor_name = Column(String)
    amount = Column(Float)
    currency = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)
    reason_for_hold = Column(String)
    review_url = Column(String)
    status = Column(String, default="PENDING")


class AuditLogModel(Base):
    """Model for audit logging"""
    __tablename__ = "audit_logs"
    
    id = Column(String, primary_key=True, index=True)
    workflow_id = Column(String, index=True)
    invoice_id = Column(String, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow)
    stage = Column(String)
    action = Column(String)
    details = Column(JSON)


# Create tables
Base.metadata.create_all(bind=engine)


def get_db():
    """Get database session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def save_checkpoint(checkpoint_data: dict) -> str:
    """Save checkpoint to database"""
    db = SessionLocal()
    try:
        checkpoint = CheckpointModel(
            checkpoint_id=checkpoint_data["checkpoint_id"],
            workflow_id=checkpoint_data["workflow_id"],
            invoice_id=checkpoint_data["invoice_id"],
            vendor_name=checkpoint_data["vendor_name"],
            amount=checkpoint_data["amount"],
            currency=checkpoint_data["currency"],
            state_blob=checkpoint_data["state_blob"],
            reason_for_hold=checkpoint_data["reason_for_hold"],
            review_url=checkpoint_data["review_url"],
        )
        db.add(checkpoint)
        db.commit()
        db.refresh(checkpoint)
        return checkpoint.checkpoint_id
    finally:
        db.close()


def get_checkpoint(checkpoint_id: str) -> dict:
    """Retrieve checkpoint from database"""
    db = SessionLocal()
    try:
        checkpoint = db.query(CheckpointModel).filter(
            CheckpointModel.checkpoint_id == checkpoint_id
        ).first()
        if checkpoint:
            return {
                "checkpoint_id": checkpoint.checkpoint_id,
                "workflow_id": checkpoint.workflow_id,
                "invoice_id": checkpoint.invoice_id,
                "vendor_name": checkpoint.vendor_name,
                "amount": checkpoint.amount,
                "currency": checkpoint.currency,
                "state_blob": checkpoint.state_blob,
                "created_at": checkpoint.created_at.isoformat(),
                "reason_for_hold": checkpoint.reason_for_hold,
                "review_url": checkpoint.review_url,
                "status": checkpoint.status,
                "reviewer_id": checkpoint.reviewer_id,
                "decision": checkpoint.decision,
                "decision_notes": checkpoint.decision_notes,
                "decided_at": checkpoint.decided_at.isoformat() if checkpoint.decided_at else None,
            }
        return None
    finally:
        db.close()


def update_checkpoint_decision(checkpoint_id: str, decision: str, reviewer_id: str, notes: str = ""):
    """Update checkpoint with human decision"""
    db = SessionLocal()
    try:
        checkpoint = db.query(CheckpointModel).filter(
            CheckpointModel.checkpoint_id == checkpoint_id
        ).first()
        if checkpoint:
            checkpoint.decision = decision
            checkpoint.reviewer_id = reviewer_id
            checkpoint.decision_notes = notes
            checkpoint.decided_at = datetime.utcnow()
            checkpoint.status = "DECIDED"
            db.commit()
    finally:
        db.close()


def get_pending_reviews() -> list:
    """Get all pending human reviews"""
    db = SessionLocal()
    try:
        reviews = db.query(HumanReviewQueueModel).filter(
            HumanReviewQueueModel.status == "PENDING"
        ).all()
        return [
            {
                "checkpoint_id": review.checkpoint_id,
                "invoice_id": review.invoice_id,
                "vendor_name": review.vendor_name,
                "amount": review.amount,
                "created_at": review.created_at.isoformat(),
                "reason_for_hold": review.reason_for_hold,
                "review_url": review.review_url,
            }
            for review in reviews
        ]
    finally:
        db.close()


def add_to_review_queue(queue_data: dict) -> str:
    """Add item to human review queue"""
    db = SessionLocal()
    try:
        review_item = HumanReviewQueueModel(
            id=queue_data["id"],
            checkpoint_id=queue_data["checkpoint_id"],
            invoice_id=queue_data["invoice_id"],
            vendor_name=queue_data["vendor_name"],
            amount=queue_data["amount"],
            currency=queue_data["currency"],
            reason_for_hold=queue_data["reason_for_hold"],
            review_url=queue_data["review_url"],
        )
        db.add(review_item)
        db.commit()
        db.refresh(review_item)
        return review_item.id
    finally:
        db.close()


def log_audit(audit_data: dict):
    """Log audit entry"""
    db = SessionLocal()
    try:
        log_entry = AuditLogModel(
            id=audit_data["id"],
            workflow_id=audit_data["workflow_id"],
            invoice_id=audit_data["invoice_id"],
            stage=audit_data["stage"],
            action=audit_data["action"],
            details=audit_data["details"],
        )
        db.add(log_entry)
        db.commit()
    finally:
        db.close()
