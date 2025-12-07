"""
Pydantic schemas for Invoice Processing Workflow
"""
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field, validator


class MatchResultEnum(str, Enum):
    MATCHED = "MATCHED"
    FAILED = "FAILED"


class HumanDecisionEnum(str, Enum):
    ACCEPT = "ACCEPT"
    REJECT = "REJECT"


class ApprovalStatusEnum(str, Enum):
    AUTO_APPROVED = "AUTO_APPROVED"
    ESCALATED = "ESCALATED"
    REJECTED = "REJECTED"


class WorkflowStatusEnum(str, Enum):
    INTAKE = "INTAKE"
    UNDERSTAND = "UNDERSTAND"
    PREPARE = "PREPARE"
    RETRIEVE = "RETRIEVE"
    MATCH_TWO_WAY = "MATCH_TWO_WAY"
    CHECKPOINT_HITL = "CHECKPOINT_HITL"
    HITL_DECISION = "HITL_DECISION"
    RECONCILE = "RECONCILE"
    APPROVE = "APPROVE"
    POSTING = "POSTING"
    NOTIFY = "NOTIFY"
    COMPLETE = "COMPLETE"
    PAUSED = "PAUSED"
    FAILED = "FAILED"


# Input Schemas
class LineItem(BaseModel):
    desc: str
    qty: float
    unit_price: float
    total: float


class InvoicePayload(BaseModel):
    invoice_id: str
    vendor_name: str
    vendor_tax_id: str
    invoice_date: str
    due_date: str
    amount: float
    currency: str
    line_items: List[LineItem]
    attachments: List[str] = []


# Stage Output Schemas
class IntakeOutput(BaseModel):
    raw_id: str
    ingest_ts: str
    validated: bool


class ParsedLineItem(BaseModel):
    desc: str
    qty: float
    unit_price: float
    total: float


class ParsedDates(BaseModel):
    invoice_date: str
    due_date: str


class ParsedInvoice(BaseModel):
    invoice_text: str
    parsed_line_items: List[ParsedLineItem]
    detected_pos: List[str]
    currency: str
    parsed_dates: ParsedDates


class UnderstandOutput(BaseModel):
    parsed_invoice: ParsedInvoice


class EnrichmentMeta(BaseModel):
    source: str
    confidence: float
    enriched_at: str


class VendorProfile(BaseModel):
    normalized_name: str
    tax_id: str
    enrichment_meta: Optional[EnrichmentMeta] = None


class NormalizedInvoice(BaseModel):
    amount: float
    currency: str
    line_items: List[ParsedLineItem]


class Flags(BaseModel):
    missing_info: List[str] = []
    risk_score: float


class PrepareOutput(BaseModel):
    vendor_profile: VendorProfile
    normalized_invoice: NormalizedInvoice
    flags: Flags


class PurchaseOrder(BaseModel):
    po_id: str
    vendor_id: str
    amount: float
    items: List[Dict[str, Any]]


class GoodsReceivedNote(BaseModel):
    grn_id: str
    po_id: str
    received_qty: float
    received_date: str


class RetrieveOutput(BaseModel):
    matched_pos: List[PurchaseOrder]
    matched_grns: List[GoodsReceivedNote]
    history: List[Dict[str, Any]]


class MatchEvidence(BaseModel):
    amount_match: bool
    po_match: bool
    vendor_match: bool
    details: Dict[str, Any]


class MatchTwoWayOutput(BaseModel):
    match_score: float
    match_result: MatchResultEnum
    tolerance_pct: float
    match_evidence: MatchEvidence


class CheckpointHitlOutput(BaseModel):
    checkpoint_id: str
    review_url: str
    paused_reason: str


class HitlDecisionOutput(BaseModel):
    human_decision: HumanDecisionEnum
    reviewer_id: str
    resume_token: str
    next_stage: str


class AccountingEntry(BaseModel):
    account_code: str
    debit: float = 0.0
    credit: float = 0.0
    description: str


class ReconciliationReport(BaseModel):
    total_debits: float
    total_credits: float
    balanced: bool
    entries_count: int


class ReconcileOutput(BaseModel):
    accounting_entries: List[AccountingEntry]
    reconciliation_report: ReconciliationReport


class ApproveOutput(BaseModel):
    approval_status: ApprovalStatusEnum
    approver_id: Optional[str] = None


class PostingOutput(BaseModel):
    posted: bool
    erp_txn_id: str
    scheduled_payment_id: str


class NotifyStatus(BaseModel):
    vendor_email: bool
    finance_team_slack: bool
    details: Dict[str, Any]


class NotifyOutput(BaseModel):
    notify_status: NotifyStatus
    notified_parties: List[str]


class FinalPayload(BaseModel):
    invoice_id: str
    vendor_name: str
    amount: float
    currency: str
    status: WorkflowStatusEnum
    erp_txn_id: str
    posted_at: str
    accounting_entries: List[AccountingEntry]


class AuditLogEntry(BaseModel):
    timestamp: str
    stage: str
    action: str
    details: Dict[str, Any]


class CompleteOutput(BaseModel):
    final_payload: FinalPayload
    audit_log: List[AuditLogEntry]
    status: WorkflowStatusEnum


# Workflow State Schema
class WorkflowState(BaseModel):
    # Metadata
    workflow_id: str
    current_stage: WorkflowStatusEnum
    created_at: str
    updated_at: str
    
    # Input
    invoice_payload: Optional[InvoicePayload] = None
    
    # Stage outputs
    intake_output: Optional[IntakeOutput] = None
    understand_output: Optional[UnderstandOutput] = None
    prepare_output: Optional[PrepareOutput] = None
    retrieve_output: Optional[RetrieveOutput] = None
    match_two_way_output: Optional[MatchTwoWayOutput] = None
    checkpoint_hitl_output: Optional[CheckpointHitlOutput] = None
    hitl_decision_output: Optional[HitlDecisionOutput] = None
    reconcile_output: Optional[ReconcileOutput] = None
    approve_output: Optional[ApproveOutput] = None
    posting_output: Optional[PostingOutput] = None
    notify_output: Optional[NotifyOutput] = None
    complete_output: Optional[CompleteOutput] = None
    
    # Execution tracking
    execution_log: List[AuditLogEntry] = []
    tool_selections: Dict[str, str] = {}
    
    class Config:
        use_enum_values = False


# Checkpoint Schema
class CheckpointRecord(BaseModel):
    checkpoint_id: str
    workflow_id: str
    invoice_id: str
    vendor_name: str
    amount: float
    currency: str
    state_blob: Dict[str, Any]
    created_at: str
    reason_for_hold: str
    review_url: str
    status: str = "PENDING"
    reviewer_id: Optional[str] = None
    decision: Optional[str] = None
    decision_notes: Optional[str] = None
    decided_at: Optional[str] = None


# Human Review API Schemas
class HumanReviewItem(BaseModel):
    checkpoint_id: str
    invoice_id: str
    vendor_name: str
    amount: float
    created_at: str
    reason_for_hold: str
    review_url: str


class HumanReviewListResponse(BaseModel):
    items: List[HumanReviewItem]


class HumanReviewDecisionRequest(BaseModel):
    checkpoint_id: str
    decision: HumanDecisionEnum
    notes: str = ""
    reviewer_id: str


class HumanReviewDecisionResponse(BaseModel):
    resume_token: str
    next_stage: str
