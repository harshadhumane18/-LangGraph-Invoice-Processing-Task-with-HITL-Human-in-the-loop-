"""
LangGraph Invoice Processing Workflow - Core Implementation
"""
import logging
import json
import uuid
from datetime import datetime
from typing import Dict, Any, Optional
from langgraph.graph import StateGraph, END
from src.schemas import (
    WorkflowState, InvoicePayload, IntakeOutput, UnderstandOutput,
    PrepareOutput, RetrieveOutput, MatchTwoWayOutput, CheckpointHitlOutput,
    HitlDecisionOutput, ReconcileOutput, ApproveOutput, PostingOutput,
    NotifyOutput, CompleteOutput, WorkflowStatusEnum, MatchResultEnum,
    HumanDecisionEnum, ApprovalStatusEnum, AuditLogEntry, ParsedInvoice,
    ParsedLineItem, ParsedDates, VendorProfile, EnrichmentMeta,
    NormalizedInvoice, Flags, PurchaseOrder, GoodsReceivedNote,
    MatchEvidence, AccountingEntry, ReconciliationReport, NotifyStatus,
    FinalPayload
)
from src.config import settings
from src.database import (
    save_checkpoint, get_checkpoint, update_checkpoint_decision,
    add_to_review_queue, log_audit
)
from src.bigtool import BigtoolPicker, common_mcp, atlas_mcp
from src.llm_utils import gemini_llm

logger = logging.getLogger(__name__)


def create_workflow_state(invoice_payload: InvoicePayload) -> WorkflowState:
    """Create initial workflow state"""
    return WorkflowState(
        workflow_id=str(uuid.uuid4()),
        current_stage=WorkflowStatusEnum.INTAKE,
        created_at=datetime.utcnow().isoformat(),
        updated_at=datetime.utcnow().isoformat(),
        invoice_payload=invoice_payload,
        execution_log=[],
        tool_selections={},
    )


def log_stage_execution(state: WorkflowState, stage: str, action: str, details: Dict[str, Any]) -> WorkflowState:
    """Log stage execution"""
    log_entry = AuditLogEntry(
        timestamp=datetime.utcnow().isoformat(),
        stage=stage,
        action=action,
        details=details,
    )
    state.execution_log.append(log_entry)
    
    # Also persist to database
    log_audit({
        "id": str(uuid.uuid4()),
        "workflow_id": state.workflow_id,
        "invoice_id": state.invoice_payload.invoice_id if state.invoice_payload else "unknown",
        "stage": stage,
        "action": action,
        "details": details,
    })
    
    return state


# ============================================================================
# STAGE 1: INTAKE - Accept and validate invoice payload
# ============================================================================
def node_intake(state: WorkflowState) -> WorkflowState:
    """INTAKE Stage: Validate payload schema, persist raw invoice"""
    logger.info(f"[INTAKE] Processing invoice: {state.invoice_payload.invoice_id}")
    
    # Select storage tool via Bigtool
    storage_tool = BigtoolPicker.select("storage")
    state.tool_selections["intake_storage"] = storage_tool
    
    # Validate schema (Pydantic already validates)
    raw_id = str(uuid.uuid4())
    ingest_ts = datetime.utcnow().isoformat()
    
    state.intake_output = IntakeOutput(
        raw_id=raw_id,
        ingest_ts=ingest_ts,
        validated=True,
    )
    
    state.current_stage = WorkflowStatusEnum.INTAKE
    state = log_stage_execution(
        state, "INTAKE", "invoice_validated",
        {"raw_id": raw_id, "invoice_id": state.invoice_payload.invoice_id}
    )
    
    logger.info(f"[INTAKE] Completed: raw_id={raw_id}")
    return state


# ============================================================================
# STAGE 2: UNDERSTAND - OCR extraction and parsing
# ============================================================================
def node_understand(state: WorkflowState) -> WorkflowState:
    """UNDERSTAND Stage: Run OCR and parse line items"""
    logger.info(f"[UNDERSTAND] Extracting invoice text")
    
    # Select OCR tool via Bigtool
    ocr_tool = BigtoolPicker.select_ocr_tool()
    state.tool_selections["understand_ocr"] = ocr_tool
    
    # Simulate OCR extraction
    invoice_text = f"""
    Invoice from {state.invoice_payload.vendor_name}
    Invoice ID: {state.invoice_payload.invoice_id}
    Date: {state.invoice_payload.invoice_date}
    Due: {state.invoice_payload.due_date}
    Amount: {state.invoice_payload.amount} {state.invoice_payload.currency}
    """
    
    # Use LLM to extract structured data
    extracted_data = gemini_llm.extract_invoice_text(invoice_text)
    
    # Parse line items
    parsed_line_items = [
        ParsedLineItem(
            desc=item.desc,
            qty=item.qty,
            unit_price=item.unit_price,
            total=item.total,
        )
        for item in state.invoice_payload.line_items
    ]
    
    parsed_invoice = ParsedInvoice(
        invoice_text=invoice_text,
        parsed_line_items=parsed_line_items,
        detected_pos=extracted_data.get("po_references", []),
        currency=state.invoice_payload.currency,
        parsed_dates=ParsedDates(
            invoice_date=state.invoice_payload.invoice_date,
            due_date=state.invoice_payload.due_date,
        ),
    )
    
    state.understand_output = UnderstandOutput(parsed_invoice=parsed_invoice)
    state.current_stage = WorkflowStatusEnum.UNDERSTAND
    state = log_stage_execution(
        state, "UNDERSTAND", "invoice_parsed",
        {"line_items_count": len(parsed_line_items), "ocr_tool": ocr_tool}
    )
    
    logger.info(f"[UNDERSTAND] Completed: {len(parsed_line_items)} line items parsed")
    return state


# ============================================================================
# STAGE 3: PREPARE - Vendor normalization and enrichment
# ============================================================================
def node_prepare(state: WorkflowState) -> WorkflowState:
    """PREPARE Stage: Normalize vendor and enrich data"""
    logger.info(f"[PREPARE] Normalizing vendor: {state.invoice_payload.vendor_name}")
    
    # Select enrichment tool via Bigtool
    enrichment_tool = BigtoolPicker.select_enrichment_tool()
    state.tool_selections["prepare_enrichment"] = enrichment_tool
    
    # Normalize vendor name using LLM
    normalized_name = gemini_llm.normalize_vendor_name(state.invoice_payload.vendor_name)
    
    # Create vendor profile
    vendor_profile = VendorProfile(
        normalized_name=normalized_name,
        tax_id=state.invoice_payload.vendor_tax_id,
        enrichment_meta=EnrichmentMeta(
            source=enrichment_tool,
            confidence=0.95,
            enriched_at=datetime.utcnow().isoformat(),
        ),
    )
    
    # Normalize invoice
    normalized_invoice = NormalizedInvoice(
        amount=state.invoice_payload.amount,
        currency=state.invoice_payload.currency,
        line_items=[
            ParsedLineItem(
                desc=item.desc,
                qty=item.qty,
                unit_price=item.unit_price,
                total=item.total,
            )
            for item in state.invoice_payload.line_items
        ],
    )
    
    # Compute flags
    flags = Flags(
        missing_info=[],
        risk_score=0.1,  # Low risk for valid invoices
    )
    
    state.prepare_output = PrepareOutput(
        vendor_profile=vendor_profile,
        normalized_invoice=normalized_invoice,
        flags=flags,
    )
    
    state.current_stage = WorkflowStatusEnum.PREPARE
    state = log_stage_execution(
        state, "PREPARE", "vendor_enriched",
        {"normalized_name": normalized_name, "enrichment_tool": enrichment_tool}
    )
    
    logger.info(f"[PREPARE] Completed: vendor normalized to '{normalized_name}'")
    return state


# ============================================================================
# STAGE 4: RETRIEVE - Fetch POs, GRNs, and history
# ============================================================================
def node_retrieve(state: WorkflowState) -> WorkflowState:
    """RETRIEVE Stage: Fetch POs and GRNs from ERP"""
    logger.info(f"[RETRIEVE] Fetching POs and GRNs")
    
    # Select ERP tool via Bigtool
    erp_tool = BigtoolPicker.select_erp_tool()
    state.tool_selections["retrieve_erp"] = erp_tool
    
    # Mock PO data
    matched_pos = [
        PurchaseOrder(
            po_id="PO-2024-001",
            vendor_id=state.invoice_payload.vendor_tax_id,
            amount=state.invoice_payload.amount,
            items=[
                {"desc": item.desc, "qty": item.qty, "unit_price": item.unit_price}
                for item in state.invoice_payload.line_items
            ],
        ),
    ]
    
    # Mock GRN data
    matched_grns = [
        GoodsReceivedNote(
            grn_id="GRN-2024-001",
            po_id="PO-2024-001",
            received_qty=sum(item.qty for item in state.invoice_payload.line_items),
            received_date=datetime.utcnow().isoformat(),
        ),
    ]
    
    state.retrieve_output = RetrieveOutput(
        matched_pos=matched_pos,
        matched_grns=matched_grns,
        history=[],
    )
    
    state.current_stage = WorkflowStatusEnum.RETRIEVE
    state = log_stage_execution(
        state, "RETRIEVE", "po_grn_fetched",
        {"pos_count": len(matched_pos), "grns_count": len(matched_grns), "erp_tool": erp_tool}
    )
    
    logger.info(f"[RETRIEVE] Completed: {len(matched_pos)} POs, {len(matched_grns)} GRNs")
    return state


# ============================================================================
# STAGE 5: MATCH_TWO_WAY - Compute 2-way match score
# ============================================================================
def node_match_two_way(state: WorkflowState) -> WorkflowState:
    """MATCH_TWO_WAY Stage: Compute match score between invoice and PO"""
    logger.info(f"[MATCH_TWO_WAY] Computing match score")
    
    # Prepare invoice and PO data for matching
    invoice_data = {
        "amount": state.invoice_payload.amount,
        "vendor_name": state.prepare_output.vendor_profile.normalized_name,
        "line_items": [
            {"desc": item.desc, "qty": item.qty, "total": item.total}
            for item in state.invoice_payload.line_items
        ],
    }
    
    po_data = {
        "amount": state.retrieve_output.matched_pos[0].amount if state.retrieve_output.matched_pos else 0,
        "vendor_id": state.retrieve_output.matched_pos[0].vendor_id if state.retrieve_output.matched_pos else "",
        "items": state.retrieve_output.matched_pos[0].items if state.retrieve_output.matched_pos else [],
    }
    
    # Compute match score using LLM
    match_score = gemini_llm.compute_match_score(invoice_data, po_data)
    
    # Determine match result
    match_result = (
        MatchResultEnum.MATCHED if match_score >= settings.MATCH_THRESHOLD
        else MatchResultEnum.FAILED
    )
    
    match_evidence = MatchEvidence(
        amount_match=abs(invoice_data["amount"] - po_data["amount"]) < 100,
        po_match=len(state.retrieve_output.matched_pos) > 0,
        vendor_match=True,
        details={"match_score": match_score},
    )
    
    state.match_two_way_output = MatchTwoWayOutput(
        match_score=match_score,
        match_result=match_result,
        tolerance_pct=settings.TWO_WAY_TOLERANCE_PCT,
        match_evidence=match_evidence,
    )
    
    state.current_stage = WorkflowStatusEnum.MATCH_TWO_WAY
    state = log_stage_execution(
        state, "MATCH_TWO_WAY", "match_computed",
        {"match_score": match_score, "match_result": match_result.value}
    )
    
    logger.info(f"[MATCH_TWO_WAY] Completed: match_score={match_score}, result={match_result.value}")
    return state


# ============================================================================
# STAGE 6: CHECKPOINT_HITL - Save state if matching fails
# ============================================================================
def node_checkpoint_hitl(state: WorkflowState) -> WorkflowState:
    """CHECKPOINT_HITL Stage: Create checkpoint if match fails"""
    
    # Only execute if match failed
    if state.match_two_way_output.match_result != MatchResultEnum.FAILED:
        logger.info(f"[CHECKPOINT_HITL] Skipped: match succeeded")
        return state
    
    logger.info(f"[CHECKPOINT_HITL] Creating checkpoint for human review")
    
    # Select DB tool via Bigtool
    db_tool = BigtoolPicker.select_db_tool()
    state.tool_selections["checkpoint_db"] = db_tool
    
    checkpoint_id = str(uuid.uuid4())
    review_url = f"http://localhost:8000/human-review/{checkpoint_id}"
    
    # Prepare state blob for persistence
    state_blob = {
        "workflow_id": state.workflow_id,
        "invoice_payload": state.invoice_payload.model_dump(),
        "intake_output": state.intake_output.model_dump() if state.intake_output else None,
        "understand_output": state.understand_output.model_dump() if state.understand_output else None,
        "prepare_output": state.prepare_output.model_dump() if state.prepare_output else None,
        "retrieve_output": state.retrieve_output.model_dump() if state.retrieve_output else None,
        "match_two_way_output": state.match_two_way_output.model_dump() if state.match_two_way_output else None,
    }
    
    # Save checkpoint to database
    checkpoint_data = {
        "checkpoint_id": checkpoint_id,
        "workflow_id": state.workflow_id,
        "invoice_id": state.invoice_payload.invoice_id,
        "vendor_name": state.prepare_output.vendor_profile.normalized_name,
        "amount": state.invoice_payload.amount,
        "currency": state.invoice_payload.currency,
        "state_blob": state_blob,
        "reason_for_hold": f"Match score {state.match_two_way_output.match_score} below threshold {settings.MATCH_THRESHOLD}",
        "review_url": review_url,
    }
    
    save_checkpoint(checkpoint_data)
    
    # Add to human review queue
    add_to_review_queue({
        "id": str(uuid.uuid4()),
        "checkpoint_id": checkpoint_id,
        "invoice_id": state.invoice_payload.invoice_id,
        "vendor_name": state.prepare_output.vendor_profile.normalized_name,
        "amount": state.invoice_payload.amount,
        "currency": state.invoice_payload.currency,
        "reason_for_hold": checkpoint_data["reason_for_hold"],
        "review_url": review_url,
    })
    
    state.checkpoint_hitl_output = CheckpointHitlOutput(
        checkpoint_id=checkpoint_id,
        review_url=review_url,
        paused_reason=checkpoint_data["reason_for_hold"],
    )
    
    state.current_stage = WorkflowStatusEnum.CHECKPOINT_HITL
    state = log_stage_execution(
        state, "CHECKPOINT_HITL", "checkpoint_created",
        {"checkpoint_id": checkpoint_id, "db_tool": db_tool}
    )
    
    logger.info(f"[CHECKPOINT_HITL] Completed: checkpoint_id={checkpoint_id}")
    return state


# ============================================================================
# STAGE 7: HITL_DECISION - Await human decision (Non-deterministic)
# ============================================================================
def node_hitl_decision(state: WorkflowState) -> WorkflowState:
    """HITL_DECISION Stage: Await human decision"""
    
    # Only execute if checkpoint was created
    if not state.checkpoint_hitl_output:
        logger.info(f"[HITL_DECISION] Skipped: no checkpoint")
        return state
    
    logger.info(f"[HITL_DECISION] Awaiting human decision for checkpoint: {state.checkpoint_hitl_output.checkpoint_id}")
    
    # In a real implementation, this would wait for human input via API
    # For demo, we'll simulate acceptance
    checkpoint = get_checkpoint(state.checkpoint_hitl_output.checkpoint_id)
    
    if checkpoint and checkpoint.get("decision"):
        human_decision = HumanDecisionEnum(checkpoint["decision"])
        reviewer_id = checkpoint.get("reviewer_id", "demo_reviewer")
    else:
        # Default to ACCEPT for demo
        human_decision = HumanDecisionEnum.ACCEPT
        reviewer_id = "demo_reviewer"
    
    next_stage = (
        WorkflowStatusEnum.RECONCILE.value if human_decision == HumanDecisionEnum.ACCEPT
        else WorkflowStatusEnum.COMPLETE.value
    )
    
    state.hitl_decision_output = HitlDecisionOutput(
        human_decision=human_decision,
        reviewer_id=reviewer_id,
        resume_token=str(uuid.uuid4()),
        next_stage=next_stage,
    )
    
    state.current_stage = WorkflowStatusEnum.HITL_DECISION
    state = log_stage_execution(
        state, "HITL_DECISION", "human_decision_received",
        {"decision": human_decision.value, "reviewer_id": reviewer_id}
    )
    
    logger.info(f"[HITL_DECISION] Completed: decision={human_decision.value}")
    return state


# ============================================================================
# STAGE 8: RECONCILE - Build accounting entries
# ============================================================================
def node_reconcile(state: WorkflowState) -> WorkflowState:
    """RECONCILE Stage: Build accounting entries"""
    
    # Skip if human rejected
    if state.hitl_decision_output and state.hitl_decision_output.human_decision == HumanDecisionEnum.REJECT:
        logger.info(f"[RECONCILE] Skipped: human rejected")
        return state
    
    # Skip if no match and no HITL decision
    if state.match_two_way_output.match_result == MatchResultEnum.FAILED and not state.hitl_decision_output:
        logger.info(f"[RECONCILE] Skipped: awaiting HITL decision")
        return state
    
    logger.info(f"[RECONCILE] Building accounting entries")
    
    # Prepare invoice data for accounting
    invoice_data = {
        "invoice_id": state.invoice_payload.invoice_id,
        "amount": state.invoice_payload.amount,
        "currency": state.invoice_payload.currency,
        "vendor": state.prepare_output.vendor_profile.normalized_name,
        "line_items": [
            {"desc": item.desc, "qty": item.qty, "total": item.total}
            for item in state.invoice_payload.line_items
        ],
    }
    
    # Generate accounting entries using LLM
    acct_data = gemini_llm.generate_accounting_entries(invoice_data)
    
    # Parse accounting entries
    accounting_entries = [
        AccountingEntry(
            account_code=entry.get("account_code", "5000"),
            debit=entry.get("debit", 0.0),
            credit=entry.get("credit", 0.0),
            description=entry.get("description", "Invoice entry"),
        )
        for entry in acct_data.get("entries", [])
    ]
    
    # If no entries from LLM, create default
    if not accounting_entries:
        accounting_entries = [
            AccountingEntry(
                account_code="2100",
                debit=0.0,
                credit=state.invoice_payload.amount,
                description=f"AP for {state.prepare_output.vendor_profile.normalized_name}",
            ),
            AccountingEntry(
                account_code="5000",
                debit=state.invoice_payload.amount,
                credit=0.0,
                description=f"Expense from {state.prepare_output.vendor_profile.normalized_name}",
            ),
        ]
    
    total_debits = sum(e.debit for e in accounting_entries)
    total_credits = sum(e.credit for e in accounting_entries)
    
    reconciliation_report = ReconciliationReport(
        total_debits=total_debits,
        total_credits=total_credits,
        balanced=abs(total_debits - total_credits) < 0.01,
        entries_count=len(accounting_entries),
    )
    
    state.reconcile_output = ReconcileOutput(
        accounting_entries=accounting_entries,
        reconciliation_report=reconciliation_report,
    )
    
    state.current_stage = WorkflowStatusEnum.RECONCILE
    state = log_stage_execution(
        state, "RECONCILE", "entries_created",
        {"entries_count": len(accounting_entries), "balanced": reconciliation_report.balanced}
    )
    
    logger.info(f"[RECONCILE] Completed: {len(accounting_entries)} entries, balanced={reconciliation_report.balanced}")
    return state


# ============================================================================
# STAGE 9: APPROVE - Apply approval policies
# ============================================================================
def node_approve(state: WorkflowState) -> WorkflowState:
    """APPROVE Stage: Apply approval policies"""
    
    # Skip if reconcile was skipped
    if not state.reconcile_output:
        logger.info(f"[APPROVE] Skipped: no reconciliation")
        return state
    
    logger.info(f"[APPROVE] Applying approval policies")
    
    approval_status = gemini_llm.determine_approval_status(
        state.invoice_payload.amount,
        settings.AUTO_APPROVE_THRESHOLD,
    )
    
    state.approve_output = ApproveOutput(
        approval_status=ApprovalStatusEnum(approval_status),
        approver_id="system" if approval_status == "AUTO_APPROVED" else "manager_001",
    )
    
    state.current_stage = WorkflowStatusEnum.APPROVE
    state = log_stage_execution(
        state, "APPROVE", "approval_determined",
        {"approval_status": approval_status, "amount": state.invoice_payload.amount}
    )
    
    logger.info(f"[APPROVE] Completed: status={approval_status}")
    return state


# ============================================================================
# STAGE 10: POSTING - Post to ERP and schedule payment
# ============================================================================
def node_posting(state: WorkflowState) -> WorkflowState:
    """POSTING Stage: Post to ERP and schedule payment"""
    
    # Skip if approve was skipped
    if not state.approve_output:
        logger.info(f"[POSTING] Skipped: no approval")
        return state
    
    logger.info(f"[POSTING] Posting to ERP")
    
    # Select ERP tool via Bigtool
    erp_tool = BigtoolPicker.select_erp_tool()
    state.tool_selections["posting_erp"] = erp_tool
    
    erp_txn_id = f"TXN-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:6]}"
    payment_id = f"PAY-{uuid.uuid4().hex[:8]}"
    
    state.posting_output = PostingOutput(
        posted=True,
        erp_txn_id=erp_txn_id,
        scheduled_payment_id=payment_id,
    )
    
    state.current_stage = WorkflowStatusEnum.POSTING
    state = log_stage_execution(
        state, "POSTING", "posted_to_erp",
        {"erp_txn_id": erp_txn_id, "payment_id": payment_id, "erp_tool": erp_tool}
    )
    
    logger.info(f"[POSTING] Completed: txn_id={erp_txn_id}")
    return state


# ============================================================================
# STAGE 11: NOTIFY - Send notifications
# ============================================================================
def node_notify(state: WorkflowState) -> WorkflowState:
    """NOTIFY Stage: Send notifications to vendor and finance team"""
    
    # Skip if posting was skipped
    if not state.posting_output:
        logger.info(f"[NOTIFY] Skipped: no posting")
        return state
    
    logger.info(f"[NOTIFY] Sending notifications")
    
    # Select email tool via Bigtool
    email_tool = BigtoolPicker.select_email_tool()
    state.tool_selections["notify_email"] = email_tool
    
    notify_status = NotifyStatus(
        vendor_email=True,
        finance_team_slack=True,
        details={
            "vendor_email": f"Invoice {state.invoice_payload.invoice_id} processed",
            "finance_team": f"Invoice posted with TXN {state.posting_output.erp_txn_id}",
        },
    )
    
    state.notify_output = NotifyOutput(
        notify_status=notify_status,
        notified_parties=[
            state.prepare_output.vendor_profile.normalized_name,
            "finance_team@company.com",
        ],
    )
    
    state.current_stage = WorkflowStatusEnum.NOTIFY
    state = log_stage_execution(
        state, "NOTIFY", "notifications_sent",
        {"parties": state.notify_output.notified_parties, "email_tool": email_tool}
    )
    
    logger.info(f"[NOTIFY] Completed: notified {len(state.notify_output.notified_parties)} parties")
    return state


# ============================================================================
# STAGE 12: COMPLETE - Output final payload
# ============================================================================
def node_complete(state: WorkflowState) -> WorkflowState:
    """COMPLETE Stage: Produce final payload and audit log"""
    logger.info(f"[COMPLETE] Finalizing workflow")
    
    # Select DB tool via Bigtool
    db_tool = BigtoolPicker.select_db_tool()
    state.tool_selections["complete_db"] = db_tool
    
    final_payload = FinalPayload(
        invoice_id=state.invoice_payload.invoice_id,
        vendor_name=state.prepare_output.vendor_profile.normalized_name if state.prepare_output else state.invoice_payload.vendor_name,
        amount=state.invoice_payload.amount,
        currency=state.invoice_payload.currency,
        status=WorkflowStatusEnum.COMPLETE,
        erp_txn_id=state.posting_output.erp_txn_id if state.posting_output else "N/A",
        posted_at=datetime.utcnow().isoformat(),
        accounting_entries=state.reconcile_output.accounting_entries if state.reconcile_output else [],
    )
    
    state.complete_output = CompleteOutput(
        final_payload=final_payload,
        audit_log=state.execution_log,
        status=WorkflowStatusEnum.COMPLETE,
    )
    
    state.current_stage = WorkflowStatusEnum.COMPLETE
    state = log_stage_execution(
        state, "COMPLETE", "workflow_completed",
        {"invoice_id": state.invoice_payload.invoice_id, "db_tool": db_tool}
    )
    
    logger.info(f"[COMPLETE] Workflow completed for invoice {state.invoice_payload.invoice_id}")
    return state


# ============================================================================
# Conditional routing logic
# ============================================================================
def should_checkpoint(state: WorkflowState) -> str:
    """Determine if we should create checkpoint"""
    if state.match_two_way_output and state.match_two_way_output.match_result == MatchResultEnum.FAILED:
        return "checkpoint"
    return "skip_checkpoint"


def should_hitl_decision(state: WorkflowState) -> str:
    """Determine if we should wait for HITL decision"""
    if state.checkpoint_hitl_output:
        return "hitl_decision"
    return "skip_hitl"


def should_reconcile(state: WorkflowState) -> str:
    """Determine if we should reconcile"""
    if state.reconcile_output:
        return "reconcile"
    if state.hitl_decision_output and state.hitl_decision_output.human_decision == HumanDecisionEnum.ACCEPT:
        return "reconcile"
    return "skip_reconcile"




# Create the compiled workflow
def create_compiled_workflow():
    """Create and return the compiled workflow"""
    workflow = StateGraph(WorkflowState)
    
    # Add all nodes
    workflow.add_node("intake", node_intake)
    workflow.add_node("understand", node_understand)
    workflow.add_node("prepare", node_prepare)
    workflow.add_node("retrieve", node_retrieve)
    workflow.add_node("match_two_way", node_match_two_way)
    workflow.add_node("checkpoint_hitl", node_checkpoint_hitl)
    workflow.add_node("hitl_decision", node_hitl_decision)
    workflow.add_node("reconcile", node_reconcile)
    workflow.add_node("approve", node_approve)
    workflow.add_node("posting", node_posting)
    workflow.add_node("notify", node_notify)
    workflow.add_node("complete", node_complete)
    
    # Set entry point
    workflow.set_entry_point("intake")
    
    # Add edges - deterministic flow
    workflow.add_edge("intake", "understand")
    workflow.add_edge("understand", "prepare")
    workflow.add_edge("prepare", "retrieve")
    workflow.add_edge("retrieve", "match_two_way")
    
    # Conditional edge after match
    workflow.add_conditional_edges(
        "match_two_way",
        should_checkpoint,
        {
            "checkpoint": "checkpoint_hitl",
            "skip_checkpoint": "reconcile",
        },
    )
    
    # Checkpoint to HITL
    workflow.add_edge("checkpoint_hitl", "hitl_decision")
    
    # HITL to reconcile
    workflow.add_edge("hitl_decision", "reconcile")
    
    # Continue flow
    workflow.add_edge("reconcile", "approve")
    workflow.add_edge("approve", "posting")
    workflow.add_edge("posting", "notify")
    workflow.add_edge("notify", "complete")
    
    # End
    workflow.add_edge("complete", END)
    
    return workflow.compile()


invoice_processing_workflow = create_compiled_workflow()
