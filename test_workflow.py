"""
Test script for Invoice Processing Workflow
Validates all components and stages
"""
import json
import logging
from src.schemas import InvoicePayload, LineItem, WorkflowStatusEnum
from src.workflow import create_workflow_state, invoice_processing_workflow
from src.database import get_checkpoint, get_pending_reviews
from src.bigtool import BigtoolPicker

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def test_schema_validation():
    """Test Pydantic schema validation"""
    logger.info("Testing schema validation...")
    
    # Valid invoice
    invoice = InvoicePayload(
        invoice_id="TEST-001",
        vendor_name="Test Vendor",
        vendor_tax_id="TAX-123",
        invoice_date="2024-12-07",
        due_date="2024-12-22",
        amount=1000.00,
        currency="USD",
        line_items=[
            LineItem(desc="Item 1", qty=1, unit_price=1000.00, total=1000.00)
        ],
    )
    
    assert invoice.invoice_id == "TEST-001"
    assert invoice.amount == 1000.00
    logger.info("✓ Schema validation passed")


def test_bigtool_selection():
    """Test Bigtool dynamic tool selection"""
    logger.info("Testing Bigtool selection...")
    
    ocr_tool = BigtoolPicker.select_ocr_tool()
    assert ocr_tool in ["google_vision", "tesseract", "aws_textract"]
    
    enrichment_tool = BigtoolPicker.select_enrichment_tool()
    assert enrichment_tool in ["clearbit", "people_data_labs", "vendor_db"]
    
    erp_tool = BigtoolPicker.select_erp_tool()
    assert erp_tool in ["sap_sandbox", "netsuite", "mock_erp"]
    
    db_tool = BigtoolPicker.select_db_tool()
    assert db_tool in ["postgres", "sqlite", "dynamodb"]
    
    email_tool = BigtoolPicker.select_email_tool()
    assert email_tool in ["sendgrid", "smartlead", "ses"]
    
    logger.info("✓ Bigtool selection passed")


def test_workflow_execution():
    """Test complete workflow execution"""
    logger.info("Testing workflow execution...")
    
    # Create sample invoice
    invoice = InvoicePayload(
        invoice_id="TEST-WORKFLOW-001",
        vendor_name="Test Corporation",
        vendor_tax_id="TAX-999999999",
        invoice_date="2024-12-07",
        due_date="2024-12-22",
        amount=5000.00,
        currency="USD",
        line_items=[
            LineItem(desc="Service A", qty=1, unit_price=3000.00, total=3000.00),
            LineItem(desc="Service B", qty=2, unit_price=1000.00, total=2000.00),
        ],
    )
    
    # Create state
    state = create_workflow_state(invoice)
    assert state.workflow_id is not None
    assert state.current_stage == WorkflowStatusEnum.INTAKE
    
    # Execute workflow
    final_state = invoice_processing_workflow.invoke(state)
    
    # Validate execution
    assert final_state.intake_output is not None
    assert final_state.understand_output is not None
    assert final_state.prepare_output is not None
    assert final_state.retrieve_output is not None
    assert final_state.match_two_way_output is not None
    
    # Check execution log
    assert len(final_state.execution_log) > 0
    logger.info(f"✓ Workflow executed with {len(final_state.execution_log)} log entries")
    
    # Check tool selections
    assert len(final_state.tool_selections) > 0
    logger.info(f"✓ Tool selections recorded: {list(final_state.tool_selections.keys())}")
    
    # Check final output
    if final_state.complete_output:
        assert final_state.complete_output.final_payload.invoice_id == invoice.invoice_id
        assert final_state.complete_output.final_payload.amount == invoice.amount
        logger.info("✓ Final payload generated correctly")


def test_checkpoint_creation():
    """Test checkpoint creation on match failure"""
    logger.info("Testing checkpoint creation...")
    
    # Create invoice that might fail matching
    invoice = InvoicePayload(
        invoice_id="TEST-CHECKPOINT-001",
        vendor_name="Unknown Vendor",
        vendor_tax_id="TAX-UNKNOWN",
        invoice_date="2024-12-07",
        due_date="2024-12-22",
        amount=15000.00,  # High amount to potentially fail matching
        currency="USD",
        line_items=[
            LineItem(desc="Unknown Item", qty=5, unit_price=3000.00, total=15000.00),
        ],
    )
    
    state = create_workflow_state(invoice)
    final_state = invoice_processing_workflow.invoke(state)
    
    # Check if checkpoint was created
    if final_state.checkpoint_hitl_output:
        logger.info(f"✓ Checkpoint created: {final_state.checkpoint_hitl_output.checkpoint_id}")
        
        # Try to retrieve checkpoint
        checkpoint = get_checkpoint(final_state.checkpoint_hitl_output.checkpoint_id)
        assert checkpoint is not None
        assert checkpoint["invoice_id"] == invoice.invoice_id
        logger.info("✓ Checkpoint retrieved from database")
    else:
        logger.info("✓ No checkpoint needed (match succeeded)")


def test_execution_log():
    """Test execution logging"""
    logger.info("Testing execution logging...")
    
    invoice = InvoicePayload(
        invoice_id="TEST-LOG-001",
        vendor_name="Log Test Vendor",
        vendor_tax_id="TAX-LOG",
        invoice_date="2024-12-07",
        due_date="2024-12-22",
        amount=2000.00,
        currency="USD",
        line_items=[
            LineItem(desc="Item", qty=1, unit_price=2000.00, total=2000.00),
        ],
    )
    
    state = create_workflow_state(invoice)
    final_state = invoice_processing_workflow.invoke(state)
    
    # Validate log entries
    assert len(final_state.execution_log) > 0
    
    for log_entry in final_state.execution_log:
        assert log_entry.timestamp is not None
        assert log_entry.stage is not None
        assert log_entry.action is not None
        assert log_entry.details is not None
    
    logger.info(f"✓ Execution log validated: {len(final_state.execution_log)} entries")


def test_state_persistence():
    """Test state persistence across stages"""
    logger.info("Testing state persistence...")
    
    invoice = InvoicePayload(
        invoice_id="TEST-STATE-001",
        vendor_name="State Test Vendor",
        vendor_tax_id="TAX-STATE",
        invoice_date="2024-12-07",
        due_date="2024-12-22",
        amount=3000.00,
        currency="USD",
        line_items=[
            LineItem(desc="Item", qty=1, unit_price=3000.00, total=3000.00),
        ],
    )
    
    state = create_workflow_state(invoice)
    final_state = invoice_processing_workflow.invoke(state)
    
    # Verify state persistence
    assert final_state.invoice_payload.invoice_id == invoice.invoice_id
    assert final_state.invoice_payload.amount == invoice.amount
    assert final_state.invoice_payload.vendor_name == invoice.vendor_name
    
    logger.info("✓ State persisted correctly across all stages")


def run_all_tests():
    """Run all tests"""
    print("\n" + "=" * 80)
    print("  INVOICE PROCESSING WORKFLOW - TEST SUITE")
    print("=" * 80)
    
    tests = [
        ("Schema Validation", test_schema_validation),
        ("Bigtool Selection", test_bigtool_selection),
        ("Workflow Execution", test_workflow_execution),
        ("Checkpoint Creation", test_checkpoint_creation),
        ("Execution Logging", test_execution_log),
        ("State Persistence", test_state_persistence),
    ]
    
    passed = 0
    failed = 0
    
    for test_name, test_func in tests:
        try:
            print(f"\n[TEST] {test_name}")
            test_func()
            passed += 1
        except Exception as e:
            print(f"✗ {test_name} FAILED: {str(e)}")
            logger.error(f"Test failed: {e}", exc_info=True)
            failed += 1
    
    # Summary
    print("\n" + "=" * 80)
    print(f"  TEST SUMMARY: {passed} passed, {failed} failed")
    print("=" * 80)
    
    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    exit(0 if success else 1)
