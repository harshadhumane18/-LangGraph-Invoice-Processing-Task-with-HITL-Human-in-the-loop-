"""
Configuration for Invoice Processing Workflow
"""
from pydantic_settings import BaseSettings
from typing import Optional, Dict, List


class Settings(BaseSettings):
    # API & Server
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    API_DEBUG: bool = True
    
    # Gemini LLM
    GEMINI_API_KEY: str
    GEMINI_MODEL: str = "gemini-2.5-flash"
    
    # Database
    DATABASE_URL: str = "sqlite:///./invoice_processing.db"
    
    # Workflow Config
    MATCH_THRESHOLD: float = 0.90
    TWO_WAY_TOLERANCE_PCT: float = 5.0
    AUTO_APPROVE_THRESHOLD: float = 10000.0  # Auto-approve invoices under this amount
    
    # Queue & Checkpoint
    HUMAN_REVIEW_QUEUE_TABLE: str = "human_review_queue"
    CHECKPOINT_TABLE: str = "checkpoints"
    
    # MCP Servers (mock for now)
    COMMON_SERVER_URL: str = "http://localhost:8001"
    ATLAS_SERVER_URL: str = "http://localhost:8002"
    
    # Bigtool Pools
    OCR_TOOLS: List[str] = ["google_vision", "tesseract", "aws_textract"]
    ENRICHMENT_TOOLS: List[str] = ["clearbit", "people_data_labs", "vendor_db"]
    ERP_TOOLS: List[str] = ["sap_sandbox", "netsuite", "mock_erp"]
    DB_TOOLS: List[str] = ["postgres", "sqlite", "dynamodb"]
    EMAIL_TOOLS: List[str] = ["sendgrid", "smartlead", "ses"]
    
    # Default tool selections
    DEFAULT_OCR_TOOL: str = "tesseract"
    DEFAULT_ENRICHMENT_TOOL: str = "vendor_db"
    DEFAULT_ERP_TOOL: str = "mock_erp"
    DEFAULT_DB_TOOL: str = "sqlite"
    DEFAULT_EMAIL_TOOL: str = "sendgrid"
    
    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
