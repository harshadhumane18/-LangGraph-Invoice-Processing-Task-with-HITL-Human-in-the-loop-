"""
Demo script for Invoice Processing Workflow
Shows end-to-end execution with sample invoice
"""
import json
import logging
from datetime import datetime, timedelta
from src.schemas import InvoicePayload, LineItem, WorkflowStatusEnum, WorkflowState
from src.workflow import create_workflow_state, invoice_processing_workflow

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def create_sample_invoice() -> InvoicePayload:
    """Create a sample invoice for testing"""
    return InvoicePayload(
        invoice_id="INV-2024-12-001",
        vendor_name="Acme Corporation",
        vendor_tax_id="TAX-123456789",
        invoice_date="2024-12-07",
        due_date="2024-12-22",
        amount=5000.00,
        currency="USD",
        line_items=[
            LineItem(desc="Software License", qty=1, unit_price=2000.00, total=2000.00),
            LineItem(desc="Support Services", qty=12, unit_price=250.00, total=3000.00),
        ],
        attachments=["invoice_scan.pdf"],
    )


def print_section(title: str):
    """Print a formatted section header"""
    print("\n" + "=" * 80)
    print(f"  {title}")
    print("=" * 80)


def print_stage_result(stage_name: str, output: dict):
    """Print stage execution result"""
    print(f"\n[{stage_name}]")
    print(json.dumps(output, indent=2, default=str))


def run_demo():
    """Run the complete demo"""
    print_section("INVOICE PROCESSING WORKFLOW - DEMO")
    
    # Create sample invoice
    print("\n[SETUP] Creating sample invoice...")
    invoice = create_sample_invoice()
    print(f"Invoice ID: {invoice.invoice_id}")
    print(f"Vendor: {invoice.vendor_name}")
    print(f"Amount: {invoice.amount} {invoice.currency}")
    print(f"Line Items: {len(invoice.line_items)}")
    
    # Create initial state
    print("\n[SETUP] Initializing workflow state...")
    state = create_workflow_state(invoice)
    print(f"Workflow ID: {state.workflow_id}")
    print(f"Initial Stage: {state.current_stage.value}")
    
    # Execute workflow
    print_section("EXECUTING WORKFLOW")
    
    try:
        final_state = invoice_processing_workflow.invoke(state)
        
        # Convert dict to WorkflowState if needed
        if isinstance(final_state, dict):
            final_state = WorkflowState(**final_state)
        
        # Print execution log
        print_section("EXECUTION LOG")
        for i, log_entry in enumerate(final_state.execution_log, 1):
            print(f"\n[{i}] {log_entry.stage} - {log_entry.action}")
            print(f"    Time: {log_entry.timestamp}")
            print(f"    Details: {json.dumps(log_entry.details, indent=6, default=str)}")
        
        # Print tool selections
        print_section("BIGTOOL SELECTIONS")
        for tool_name, selected_tool in final_state.tool_selections.items():
            print(f"  {tool_name}: {selected_tool}")
        
        # Print stage outputs
        print_section("STAGE OUTPUTS")
        
        if final_state.intake_output:
            print_stage_result("INTAKE", final_state.intake_output.model_dump())
        
        if final_state.understand_output:
            print_stage_result("UNDERSTAND", {
                "parsed_invoice": {
                    "currency": final_state.understand_output.parsed_invoice.currency,
                    "line_items_count": len(final_state.understand_output.parsed_invoice.parsed_line_items),
                    "detected_pos": final_state.understand_output.parsed_invoice.detected_pos,
                }
            })
        
        if final_state.prepare_output:
            print_stage_result("PREPARE", {
                "vendor_profile": {
                    "normalized_name": final_state.prepare_output.vendor_profile.normalized_name,
                    "tax_id": final_state.prepare_output.vendor_profile.tax_id,
                },
                "flags": final_state.prepare_output.flags.model_dump(),
            })
        
        if final_state.retrieve_output:
            print_stage_result("RETRIEVE", {
                "matched_pos_count": len(final_state.retrieve_output.matched_pos),
                "matched_grns_count": len(final_state.retrieve_output.matched_grns),
            })
        
        if final_state.match_two_way_output:
            print_stage_result("MATCH_TWO_WAY", {
                "match_score": final_state.match_two_way_output.match_score,
                "match_result": final_state.match_two_way_output.match_result.value,
                "tolerance_pct": final_state.match_two_way_output.tolerance_pct,
            })
        
        # Check if paused for HITL
        if final_state.checkpoint_hitl_output:
            print_section("WORKFLOW PAUSED FOR HUMAN REVIEW")
            print(f"Checkpoint ID: {final_state.checkpoint_hitl_output.checkpoint_id}")
            print(f"Review URL: {final_state.checkpoint_hitl_output.review_url}")
            print(f"Reason: {final_state.checkpoint_hitl_output.paused_reason}")
            print("\nTo resume:")
            print(f"  POST /human-review/decision")
            print(f"  Body: {{'checkpoint_id': '{final_state.checkpoint_hitl_output.checkpoint_id}', 'decision': 'ACCEPT', 'reviewer_id': 'demo_reviewer', 'notes': ''}}")
        
        if final_state.reconcile_output:
            print_stage_result("RECONCILE", {
                "accounting_entries_count": len(final_state.reconcile_output.accounting_entries),
                "reconciliation_report": final_state.reconcile_output.reconciliation_report.model_dump(),
            })
        
        if final_state.approve_output:
            print_stage_result("APPROVE", {
                "approval_status": final_state.approve_output.approval_status.value,
                "approver_id": final_state.approve_output.approver_id,
            })
        
        if final_state.posting_output:
            print_stage_result("POSTING", {
                "posted": final_state.posting_output.posted,
                "erp_txn_id": final_state.posting_output.erp_txn_id,
                "scheduled_payment_id": final_state.posting_output.scheduled_payment_id,
            })
        
        if final_state.notify_output:
            print_stage_result("NOTIFY", {
                "notify_status": final_state.notify_output.notify_status.model_dump(),
                "notified_parties": final_state.notify_output.notified_parties,
            })
        
        # Print final payload
        if final_state.complete_output:
            print_section("FINAL PAYLOAD")
            final_payload = final_state.complete_output.final_payload.model_dump()
            print(json.dumps(final_payload, indent=2, default=str))
        
        # Summary
        print_section("WORKFLOW SUMMARY")
        print(f"Workflow ID: {final_state.workflow_id}")
        print(f"Invoice ID: {invoice.invoice_id}")
        print(f"Final Status: {final_state.current_stage.value}")
        print(f"Total Stages Executed: {len(final_state.execution_log)}")
        print(f"Total Tool Selections: {len(final_state.tool_selections)}")
        print(f"Execution Time: {final_state.updated_at}")
        
        print_section("DEMO COMPLETED SUCCESSFULLY")
        
    except Exception as e:
        logger.error(f"Error during workflow execution: {e}", exc_info=True)
        print_section("ERROR OCCURRED")
        print(f"Error: {str(e)}")
        raise


if __name__ == "__main__":
    run_demo()
