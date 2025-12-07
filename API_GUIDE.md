# Invoice Processing API - Complete Guide

## Overview

The Invoice Processing Agent exposes a REST API for:
1. Processing invoices through the complete workflow
2. Managing human review checkpoints
3. Submitting human decisions
4. Retrieving workflow status and logs

## Base URL

```
http://localhost:8000
```

## Authentication

Currently no authentication is implemented. In production, add:
- JWT tokens
- API keys
- OAuth 2.0

## Endpoints

### 1. Process Invoice

**Endpoint:** `POST /process-invoice`

**Description:** Submit an invoice for processing through the complete workflow.

**Request Body:**
```json
{
  "invoice_id": "INV-2024-12-001",
  "vendor_name": "Acme Corporation",
  "vendor_tax_id": "TAX-123456789",
  "invoice_date": "2024-12-07",
  "due_date": "2024-12-22",
  "amount": 5000.00,
  "currency": "USD",
  "line_items": [
    {
      "desc": "Software License",
      "qty": 1,
      "unit_price": 2000.00,
      "total": 2000.00
    },
    {
      "desc": "Support Services",
      "qty": 12,
      "unit_price": 250.00,
      "total": 3000.00
    }
  ],
  "attachments": ["invoice_scan.pdf", "po_reference.pdf"]
}
```

**Response (Success - Match Passed):**
```json
{
  "status": "COMPLETED",
  "workflow_id": "550e8400-e29b-41d4-a716-446655440000",
  "final_payload": {
    "invoice_id": "INV-2024-12-001",
    "vendor_name": "Acme Corporation",
    "amount": 5000.00,
    "currency": "USD",
    "status": "COMPLETE",
    "erp_txn_id": "TXN-20241207103007-abc123",
    "posted_at": "2024-12-07T10:30:09.012345",
    "accounting_entries": [
      {
        "account_code": "2100",
        "debit": 0.0,
        "credit": 5000.00,
        "description": "AP for Acme Corporation"
      },
      {
        "account_code": "5000",
        "debit": 5000.00,
        "credit": 0.0,
        "description": "Expense from Acme Corporation"
      }
    ]
  },
  "audit_log": [
    {
      "timestamp": "2024-12-07T10:30:00.123456",
      "stage": "INTAKE",
      "action": "invoice_validated",
      "details": {
        "raw_id": "uuid",
        "invoice_id": "INV-2024-12-001"
      }
    },
    ...
  ],
  "tool_selections": {
    "intake_storage": "s3",
    "understand_ocr": "tesseract",
    "prepare_enrichment": "vendor_db",
    "retrieve_erp": "mock_erp",
    "checkpoint_db": "sqlite",
    "posting_erp": "mock_erp",
    "notify_email": "sendgrid",
    "complete_db": "sqlite"
  }
}
```

**Response (Paused - Match Failed):**
```json
{
  "status": "PAUSED_FOR_REVIEW",
  "checkpoint_id": "ckpt-550e8400-e29b-41d4-a716",
  "review_url": "http://localhost:8000/human-review/ckpt-550e8400-e29b-41d4-a716",
  "reason": "Match score 0.65 below threshold 0.90",
  "workflow_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

**Status Codes:**
- `200` - Invoice processed successfully
- `400` - Invalid request body
- `500` - Server error during processing

---

### 2. List Pending Reviews

**Endpoint:** `GET /human-review/pending`

**Description:** Get all invoices awaiting human review.

**Query Parameters:** None

**Response:**
```json
{
  "items": [
    {
      "checkpoint_id": "ckpt-550e8400-e29b-41d4-a716",
      "invoice_id": "INV-2024-12-001",
      "vendor_name": "Acme Corporation",
      "amount": 5000.00,
      "created_at": "2024-12-07T10:30:05.678901",
      "reason_for_hold": "Match score 0.65 below threshold 0.90",
      "review_url": "http://localhost:8000/human-review/ckpt-550e8400-e29b-41d4-a716"
    },
    {
      "checkpoint_id": "ckpt-660e8400-e29b-41d4-a716",
      "invoice_id": "INV-2024-12-002",
      "vendor_name": "Beta Inc",
      "amount": 3500.00,
      "created_at": "2024-12-07T11:15:23.456789",
      "reason_for_hold": "Vendor not found in database",
      "review_url": "http://localhost:8000/human-review/ckpt-660e8400-e29b-41d4-a716"
    }
  ]
}
```

**Status Codes:**
- `200` - Successfully retrieved pending reviews
- `500` - Server error

---

### 3. Get Review Details

**Endpoint:** `GET /human-review/{checkpoint_id}`

**Description:** Get detailed information about a specific checkpoint for review.

**Path Parameters:**
- `checkpoint_id` (string, required) - The checkpoint ID

**Response:**
```json
{
  "checkpoint_id": "ckpt-550e8400-e29b-41d4-a716",
  "workflow_id": "550e8400-e29b-41d4-a716-446655440000",
  "invoice_id": "INV-2024-12-001",
  "vendor_name": "Acme Corporation",
  "amount": 5000.00,
  "currency": "USD",
  "state_blob": {
    "workflow_id": "550e8400-e29b-41d4-a716-446655440000",
    "invoice_payload": {
      "invoice_id": "INV-2024-12-001",
      "vendor_name": "Acme Corporation",
      "vendor_tax_id": "TAX-123456789",
      "invoice_date": "2024-12-07",
      "due_date": "2024-12-22",
      "amount": 5000.00,
      "currency": "USD",
      "line_items": [
        {
          "desc": "Software License",
          "qty": 1,
          "unit_price": 2000.00,
          "total": 2000.00
        }
      ],
      "attachments": ["invoice_scan.pdf"]
    },
    "intake_output": {
      "raw_id": "uuid",
      "ingest_ts": "2024-12-07T10:30:00.123456",
      "validated": true
    },
    "understand_output": {
      "parsed_invoice": {
        "invoice_text": "...",
        "parsed_line_items": [...],
        "detected_pos": ["PO-2024-001"],
        "currency": "USD",
        "parsed_dates": {
          "invoice_date": "2024-12-07",
          "due_date": "2024-12-22"
        }
      }
    },
    "prepare_output": {
      "vendor_profile": {
        "normalized_name": "Acme Corporation",
        "tax_id": "TAX-123456789",
        "enrichment_meta": {
          "source": "vendor_db",
          "confidence": 0.95,
          "enriched_at": "2024-12-07T10:30:02.345678"
        }
      },
      "normalized_invoice": {
        "amount": 5000.00,
        "currency": "USD",
        "line_items": [...]
      },
      "flags": {
        "missing_info": [],
        "risk_score": 0.1
      }
    },
    "retrieve_output": {
      "matched_pos": [
        {
          "po_id": "PO-2024-001",
          "vendor_id": "TAX-123456789",
          "amount": 5000.00,
          "items": [...]
        }
      ],
      "matched_grns": [
        {
          "grn_id": "GRN-2024-001",
          "po_id": "PO-2024-001",
          "received_qty": 1.0,
          "received_date": "2024-12-07T10:30:03.456789"
        }
      ],
      "history": []
    },
    "match_two_way_output": {
      "match_score": 0.65,
      "match_result": "FAILED",
      "tolerance_pct": 5.0,
      "match_evidence": {
        "amount_match": false,
        "po_match": true,
        "vendor_match": true,
        "details": {
          "match_score": 0.65
        }
      }
    }
  },
  "created_at": "2024-12-07T10:30:05.678901",
  "reason_for_hold": "Match score 0.65 below threshold 0.90",
  "review_url": "http://localhost:8000/human-review/ckpt-550e8400-e29b-41d4-a716",
  "status": "PENDING",
  "reviewer_id": null,
  "decision": null,
  "decision_notes": null,
  "decided_at": null
}
```

**Status Codes:**
- `200` - Successfully retrieved checkpoint details
- `404` - Checkpoint not found
- `500` - Server error

---

### 4. Submit Human Decision

**Endpoint:** `POST /human-review/decision`

**Description:** Submit a human decision (ACCEPT/REJECT) for a checkpoint.

**Request Body:**
```json
{
  "checkpoint_id": "ckpt-550e8400-e29b-41d4-a716",
  "decision": "ACCEPT",
  "notes": "Verified with vendor. Discrepancy in line items explained. Amount is correct.",
  "reviewer_id": "john_doe"
}
```

**Response:**
```json
{
  "resume_token": "token-ckpt-550e8400-e29b-41d4-a716",
  "next_stage": "RECONCILE"
}
```

**Request Body (Rejection):**
```json
{
  "checkpoint_id": "ckpt-550e8400-e29b-41d4-a716",
  "decision": "REJECT",
  "notes": "Vendor not authorized. Invoice appears fraudulent.",
  "reviewer_id": "jane_smith"
}
```

**Response (Rejection):**
```json
{
  "resume_token": "token-ckpt-550e8400-e29b-41d4-a716",
  "next_stage": "COMPLETE"
}
```

**Status Codes:**
- `200` - Decision submitted successfully
- `404` - Checkpoint not found
- `400` - Invalid decision value
- `500` - Server error

---

### 5. Health Check

**Endpoint:** `GET /health`

**Description:** Check API health status.

**Response:**
```json
{
  "status": "healthy",
  "service": "Invoice Processing Agent with HITL",
  "version": "1.0.0"
}
```

**Status Codes:**
- `200` - API is healthy

---

### 6. Get Configuration

**Endpoint:** `GET /config`

**Description:** Get current workflow configuration.

**Response:**
```json
{
  "match_threshold": 0.90,
  "two_way_tolerance_pct": 5.0,
  "auto_approve_threshold": 10000.0,
  "gemini_model": "gemini-2.5-flash",
  "database_url": "sqlite:///./invoice_processing.db",
  "bigtool_pools": {
    "ocr": ["google_vision", "tesseract", "aws_textract"],
    "enrichment": ["clearbit", "people_data_labs", "vendor_db"],
    "erp": ["sap_sandbox", "netsuite", "mock_erp"],
    "db": ["postgres", "sqlite", "dynamodb"],
    "email": ["sendgrid", "smartlead", "ses"]
  }
}
```

**Status Codes:**
- `200` - Configuration retrieved successfully

---

## Usage Examples

### Example 1: Process Invoice (Success Path)

```bash
curl -X POST http://localhost:8000/process-invoice \
  -H "Content-Type: application/json" \
  -d '{
    "invoice_id": "INV-2024-12-001",
    "vendor_name": "Acme Corporation",
    "vendor_tax_id": "TAX-123456789",
    "invoice_date": "2024-12-07",
    "due_date": "2024-12-22",
    "amount": 5000.00,
    "currency": "USD",
    "line_items": [
      {
        "desc": "Software License",
        "qty": 1,
        "unit_price": 5000.00,
        "total": 5000.00
      }
    ],
    "attachments": []
  }'
```

### Example 2: Check Pending Reviews

```bash
curl -X GET http://localhost:8000/human-review/pending
```

### Example 3: Get Review Details

```bash
curl -X GET http://localhost:8000/human-review/ckpt-550e8400-e29b-41d4-a716
```

### Example 4: Submit Approval Decision

```bash
curl -X POST http://localhost:8000/human-review/decision \
  -H "Content-Type: application/json" \
  -d '{
    "checkpoint_id": "ckpt-550e8400-e29b-41d4-a716",
    "decision": "ACCEPT",
    "notes": "Verified with vendor",
    "reviewer_id": "john_doe"
  }'
```

### Example 5: Submit Rejection Decision

```bash
curl -X POST http://localhost:8000/human-review/decision \
  -H "Content-Type: application/json" \
  -d '{
    "checkpoint_id": "ckpt-550e8400-e29b-41d4-a716",
    "decision": "REJECT",
    "notes": "Vendor not authorized",
    "reviewer_id": "jane_smith"
  }'
```

## Error Handling

### Common Error Responses

**400 Bad Request:**
```json
{
  "detail": "Invalid request body"
}
```

**404 Not Found:**
```json
{
  "detail": "Checkpoint not found"
}
```

**500 Internal Server Error:**
```json
{
  "detail": "Error processing invoice: [error message]"
}
```

## Rate Limiting

Currently not implemented. In production, add:
- Per-user rate limits
- Per-IP rate limits
- Exponential backoff for retries

## Pagination

Currently not implemented. For large result sets, add:
- `limit` and `offset` parameters
- Cursor-based pagination

## Filtering

For `GET /human-review/pending`, consider adding:
- `status` filter (PENDING, DECIDED, etc.)
- `created_after` and `created_before` filters
- `vendor_name` search

## Sorting

For list endpoints, add:
- `sort_by` parameter (created_at, amount, vendor_name)
- `sort_order` parameter (asc, desc)

## Webhooks

Consider implementing webhooks for:
- Workflow completion
- HITL checkpoint creation
- Human decision submission

## SDK/Client Libraries

Consider creating SDKs for:
- Python
- JavaScript/TypeScript
- Go
- Java

## API Versioning

Current version: `v1.0`

Future versions should use:
- `/api/v2/process-invoice`
- `/api/v2/human-review/pending`
- etc.

## Documentation

- **Swagger/OpenAPI**: Available at `/docs`
- **ReDoc**: Available at `/redoc`
- **OpenAPI JSON**: Available at `/openapi.json`
