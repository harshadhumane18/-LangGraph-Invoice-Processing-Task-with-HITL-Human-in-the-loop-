# Quick Start Guide - Invoice Processing Agent

## 🚀 5-Minute Setup

### Step 1: Install Dependencies
```bash
pip install -r requirements.txt
```

### Step 2: Configure Environment
Edit `.env` file and add your Gemini API key:
```env
GEMINI_API_KEY=your_gemini_api_key_here
```

### Step 3: Run Demo
```bash
python demo.py
```

This will:
- Create a sample invoice
- Execute all 12 workflow stages
- Display execution logs
- Show tool selections
- Output final payload

**Expected Output:**
```
================================================================================
  INVOICE PROCESSING WORKFLOW - DEMO
================================================================================

[SETUP] Creating sample invoice...
Invoice ID: INV-2024-12-001
Vendor: Acme Corporation
Amount: 5000.0 USD
Line Items: 2

[SETUP] Initializing workflow state...
Workflow ID: [uuid]
Initial Stage: INTAKE

================================================================================
  EXECUTING WORKFLOW
================================================================================

[INTAKE] Processing invoice: INV-2024-12-001
[INTAKE] Completed: raw_id=[uuid]

[UNDERSTAND] Extracting invoice text
[UNDERSTAND] Completed: 2 line items parsed

... (continues through all 12 stages)

================================================================================
  WORKFLOW SUMMARY
================================================================================

Workflow ID: [uuid]
Invoice ID: INV-2024-12-001
Final Status: COMPLETE
Total Stages Executed: 12
Total Tool Selections: 8
```

---

## 🌐 Start API Server

```bash
python -m uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
```

Access:
- **API Docs:** http://localhost:8000/docs
- **ReDoc:** http://localhost:8000/redoc
- **Health:** http://localhost:8000/health

---

## 📝 Process Your First Invoice

### Using cURL:
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

### Using Python:
```python
import requests

invoice = {
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
}

response = requests.post(
    "http://localhost:8000/process-invoice",
    json=invoice
)

print(response.json())
```

---

## 🔍 Check Pending Reviews

```bash
curl http://localhost:8000/human-review/pending
```

Response:
```json
{
  "items": [
    {
      "checkpoint_id": "ckpt-uuid",
      "invoice_id": "INV-2024-12-001",
      "vendor_name": "Acme Corporation",
      "amount": 5000.00,
      "created_at": "2024-12-07T10:30:05",
      "reason_for_hold": "Match score 0.65 below threshold 0.90",
      "review_url": "http://localhost:8000/human-review/ckpt-uuid"
    }
  ]
}
```

---

## 👤 Submit Human Decision

```bash
curl -X POST http://localhost:8000/human-review/decision \
  -H "Content-Type: application/json" \
  -d '{
    "checkpoint_id": "ckpt-uuid",
    "decision": "ACCEPT",
    "notes": "Verified with vendor",
    "reviewer_id": "john_doe"
  }'
```

Response:
```json
{
  "resume_token": "token-ckpt-uuid",
  "next_stage": "RECONCILE"
}
```

---

## 🧪 Run Tests

```bash
python test_workflow.py
```

Expected output:
```
================================================================================
  INVOICE PROCESSING WORKFLOW - TEST SUITE
================================================================================

[TEST] Schema Validation
✓ Schema validation passed

[TEST] Bigtool Selection
✓ Bigtool selection passed

[TEST] Workflow Execution
✓ Workflow executed with 12 log entries
✓ Tool selections recorded: [...]
✓ Final payload generated correctly

[TEST] Checkpoint Creation
✓ Checkpoint created: [uuid]
✓ Checkpoint retrieved from database

[TEST] Execution Logging
✓ Execution log validated: 12 entries

[TEST] State Persistence
✓ State persisted correctly across all stages

================================================================================
  TEST SUMMARY: 6 passed, 0 failed
================================================================================
```

---

## 📊 View Execution Logs

### Via Database:
```python
from src.database import SessionLocal, AuditLogModel

db = SessionLocal()
logs = db.query(AuditLogModel).all()

for log in logs:
    print(f"[{log.stage}] {log.action}")
    print(f"  Time: {log.timestamp}")
    print(f"  Details: {log.details}")
```

### Via API:
```bash
# Get review details (includes state blob with all logs)
curl http://localhost:8000/human-review/{checkpoint_id}
```

---

## 🔧 Configuration

### Key Settings (.env)
```env
# LLM
GEMINI_API_KEY=your_key_here
GEMINI_MODEL=gemini-2.5-flash

# Workflow
MATCH_THRESHOLD=0.90
AUTO_APPROVE_THRESHOLD=10000.0

# Database
DATABASE_URL=sqlite:///./invoice_processing.db

# API
API_HOST=0.0.0.0
API_PORT=8000
API_DEBUG=True
```

### Change Match Threshold
Edit `.env`:
```env
MATCH_THRESHOLD=0.85  # Lower threshold = fewer HITL reviews
```

### Use PostgreSQL
Edit `.env`:
```env
DATABASE_URL=postgresql://user:password@localhost:5432/invoices
```

---

## 📁 Project Structure

```
windsurd_proj/
├── src/
│   ├── schemas.py          # Data models
│   ├── config.py           # Configuration
│   ├── database.py         # Database layer
│   ├── llm_utils.py        # Gemini integration
│   ├── bigtool.py          # Tool selection
│   ├── workflow.py         # LangGraph workflow
│   └── main.py             # FastAPI app
├── .env                    # Configuration
├── requirements.txt        # Dependencies
├── demo.py                 # Demo script
├── test_workflow.py        # Tests
├── workflow_config.json    # Workflow definition
├── README.md               # Full documentation
├── API_GUIDE.md            # API reference
├── IMPLEMENTATION_SUMMARY.md # Implementation details
└── QUICKSTART.md           # This file
```

---

## 🐛 Troubleshooting

### Issue: `ModuleNotFoundError: No module named 'langgraph'`
**Solution:**
```bash
pip install -r requirements.txt
```

### Issue: `GEMINI_API_KEY not found`
**Solution:**
1. Get API key from https://makersuite.google.com/app/apikey
2. Add to `.env`:
   ```env
   GEMINI_API_KEY=your_key_here
   ```

### Issue: `Database is locked`
**Solution:**
- Close other processes using the database
- Or switch to PostgreSQL in `.env`

### Issue: Port 8000 already in use
**Solution:**
```bash
python -m uvicorn src.main:app --port 8001
```

### Issue: Workflow not progressing
**Solution:**
1. Check logs in database:
   ```python
   from src.database import SessionLocal, AuditLogModel
   db = SessionLocal()
   for log in db.query(AuditLogModel).all():
       print(log)
   ```
2. Enable debug mode in `.env`:
   ```env
   API_DEBUG=True
   ```

---

## 📚 Next Steps

1. **Read Full Documentation**
   - `README.md` - Complete overview
   - `API_GUIDE.md` - All endpoints
   - `IMPLEMENTATION_SUMMARY.md` - Technical details

2. **Explore Code**
   - `src/workflow.py` - Core workflow logic
   - `src/main.py` - API implementation
   - `src/schemas.py` - Data models

3. **Customize**
   - Modify tool pools in `src/config.py`
   - Adjust workflow stages in `src/workflow.py`
   - Add new endpoints in `src/main.py`

4. **Deploy**
   - Docker: See `README.md`
   - Kubernetes: Add deployment manifests
   - Cloud: Deploy to AWS/GCP/Azure

---

## 💡 Tips & Tricks

### View All Pending Reviews
```bash
curl http://localhost:8000/human-review/pending | python -m json.tool
```

### Get API Documentation
```bash
# Swagger UI
open http://localhost:8000/docs

# ReDoc
open http://localhost:8000/redoc

# OpenAPI JSON
curl http://localhost:8000/openapi.json
```

### Run Demo with Logging
```bash
import logging
logging.basicConfig(level=logging.DEBUG)
exec(open('demo.py').read())
```

### Test with Different Invoice Amounts
```python
# Edit demo.py and change:
amount=15000.00  # Will trigger HITL (above threshold)
```

### Monitor Database
```bash
# SQLite
sqlite3 invoice_processing.db

# View tables
.tables

# View checkpoints
SELECT * FROM checkpoints;

# View audit logs
SELECT * FROM audit_logs;
```

---

## 🎯 Common Workflows

### Workflow 1: Process Invoice (Success Path)
```
1. POST /process-invoice
2. Workflow executes all 12 stages
3. Returns final payload
4. ✅ Complete
```

### Workflow 2: Process Invoice (HITL Path)
```
1. POST /process-invoice
2. Match fails → Checkpoint created
3. GET /human-review/pending
4. GET /human-review/{checkpoint_id}
5. POST /human-review/decision (ACCEPT)
6. Workflow resumes and completes
7. ✅ Complete
```

### Workflow 3: Reject Invoice
```
1. POST /process-invoice
2. Match fails → Checkpoint created
3. GET /human-review/pending
4. POST /human-review/decision (REJECT)
5. Workflow finalizes with MANUAL_HANDOFF status
6. ✅ Complete
```

---

## 📞 Support

- **Documentation:** See `README.md` and `API_GUIDE.md`
- **Issues:** Check `IMPLEMENTATION_SUMMARY.md` troubleshooting
- **Code:** Review comments in `src/workflow.py`
- **Tests:** Run `test_workflow.py` for validation

---

**You're all set! 🎉**

Start with:
```bash
python demo.py
```

Then explore the API:
```bash
python -m uvicorn src.main:app --reload
```

Visit: http://localhost:8000/docs
