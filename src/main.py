"""
FastAPI application for Invoice Processing Workflow with HITL
"""
import logging
import json
from typing import List
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from src.config import settings
from src.schemas import (
    InvoicePayload, HumanReviewListResponse, HumanReviewItem,
    HumanReviewDecisionRequest, HumanReviewDecisionResponse,
    WorkflowState, CompleteOutput
)
from src.workflow import create_workflow_state, invoice_processing_workflow
from src.database import get_pending_reviews, get_checkpoint, update_checkpoint_decision

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="Invoice Processing Agent with HITL",
    description="LangGraph-based invoice processing with Human-In-The-Loop checkpoints",
    version="1.0.0",
)


# ============================================================================
# Workflow Execution Endpoints
# ============================================================================

@app.post("/process-invoice")
async def process_invoice(invoice_payload: InvoicePayload) -> dict:
    """
    Process an invoice through the complete workflow.
    
    Returns:
    - If match succeeds: Final payload with all processing results
    - If match fails: Checkpoint info with review URL
    """
    logger.info(f"Processing invoice: {invoice_payload.invoice_id}")
    
    try:
        # Create initial workflow state
        state = create_workflow_state(invoice_payload)
        
        # Execute workflow
        final_state = invoice_processing_workflow.invoke(state)
        
        # Check if workflow completed or paused at HITL
        if final_state.checkpoint_hitl_output:
            return {
                "status": "PAUSED_FOR_REVIEW",
                "checkpoint_id": final_state.checkpoint_hitl_output.checkpoint_id,
                "review_url": final_state.checkpoint_hitl_output.review_url,
                "reason": final_state.checkpoint_hitl_output.paused_reason,
                "workflow_id": final_state.workflow_id,
            }
        
        # Return final payload
        if final_state.complete_output:
            return {
                "status": "COMPLETED",
                "workflow_id": final_state.workflow_id,
                "final_payload": final_state.complete_output.final_payload.model_dump(),
                "audit_log": [log.model_dump() for log in final_state.complete_output.audit_log],
                "tool_selections": final_state.tool_selections,
            }
        
        return {
            "status": "COMPLETED",
            "workflow_id": final_state.workflow_id,
            "message": "Workflow executed successfully",
        }
    
    except Exception as e:
        logger.error(f"Error processing invoice: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Human Review Endpoints
# ============================================================================

@app.get("/human-review/pending", response_model=HumanReviewListResponse)
async def list_pending_reviews() -> HumanReviewListResponse:
    """
    List all pending human reviews.
    
    Returns:
    - List of checkpoints awaiting human decision
    """
    logger.info("Fetching pending reviews")
    
    try:
        pending_items = get_pending_reviews()
        items = [
            HumanReviewItem(
                checkpoint_id=item["checkpoint_id"],
                invoice_id=item["invoice_id"],
                vendor_name=item["vendor_name"],
                amount=item["amount"],
                created_at=item["created_at"],
                reason_for_hold=item["reason_for_hold"],
                review_url=item["review_url"],
            )
            for item in pending_items
        ]
        return HumanReviewListResponse(items=items)
    
    except Exception as e:
        logger.error(f"Error fetching pending reviews: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/human-review/{checkpoint_id}")
async def get_review_details(checkpoint_id: str) -> dict:
    """
    Get detailed information about a specific checkpoint for review.
    
    Args:
    - checkpoint_id: The checkpoint ID to retrieve
    
    Returns:
    - Checkpoint details including state blob for review
    """
    logger.info(f"Fetching review details for checkpoint: {checkpoint_id}")
    
    try:
        checkpoint = get_checkpoint(checkpoint_id)
        if not checkpoint:
            raise HTTPException(status_code=404, detail="Checkpoint not found")
        
        return checkpoint
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching checkpoint: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/human-review/decision", response_model=HumanReviewDecisionResponse)
async def submit_human_decision(request: HumanReviewDecisionRequest) -> HumanReviewDecisionResponse:
    """
    Submit human decision (ACCEPT/REJECT) for a checkpoint.
    
    Args:
    - checkpoint_id: The checkpoint ID
    - decision: ACCEPT or REJECT
    - notes: Optional review notes
    - reviewer_id: ID of the reviewer
    
    Returns:
    - Resume token and next stage for workflow continuation
    """
    logger.info(f"Submitting decision for checkpoint: {request.checkpoint_id}")
    
    try:
        # Validate checkpoint exists
        checkpoint = get_checkpoint(request.checkpoint_id)
        if not checkpoint:
            raise HTTPException(status_code=404, detail="Checkpoint not found")
        
        # Update checkpoint with decision
        update_checkpoint_decision(
            request.checkpoint_id,
            request.decision.value,
            request.reviewer_id,
            request.notes,
        )
        
        logger.info(f"Decision recorded: {request.decision.value} by {request.reviewer_id}")
        
        # Determine next stage based on decision
        next_stage = "RECONCILE" if request.decision.value == "ACCEPT" else "COMPLETE"
        
        return HumanReviewDecisionResponse(
            resume_token=f"token-{request.checkpoint_id}",
            next_stage=next_stage,
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error submitting decision: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Health & Info Endpoints
# ============================================================================

@app.get("/health")
async def health_check() -> dict:
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "Invoice Processing Agent with HITL",
        "version": "1.0.0",
    }


@app.get("/config")
async def get_config() -> dict:
    """Get workflow configuration"""
    return {
        "match_threshold": settings.MATCH_THRESHOLD,
        "two_way_tolerance_pct": settings.TWO_WAY_TOLERANCE_PCT,
        "auto_approve_threshold": settings.AUTO_APPROVE_THRESHOLD,
        "gemini_model": settings.GEMINI_MODEL,
        "database_url": settings.DATABASE_URL,
        "bigtool_pools": {
            "ocr": settings.OCR_TOOLS,
            "enrichment": settings.ENRICHMENT_TOOLS,
            "erp": settings.ERP_TOOLS,
            "db": settings.DB_TOOLS,
            "email": settings.EMAIL_TOOLS,
        },
    }


# ============================================================================
# Root endpoint
# ============================================================================

@app.get("/")
async def root() -> dict:
    """Root endpoint with API documentation"""
    return {
        "service": "Invoice Processing Agent with HITL",
        "version": "1.0.0",
        "endpoints": {
            "process_invoice": "POST /process-invoice",
            "list_pending_reviews": "GET /human-review/pending",
            "get_review_details": "GET /human-review/{checkpoint_id}",
            "submit_decision": "POST /human-review/decision",
            "health": "GET /health",
            "config": "GET /config",
        },
        "docs": "/docs",
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app,
        host=settings.API_HOST,
        port=settings.API_PORT,
        reload=settings.API_DEBUG,
    )
