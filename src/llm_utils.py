"""
LLM utilities for Gemini 2.5 Flash integration
"""
import json
import logging
from typing import Any, Dict
from langchain_google_genai import ChatGoogleGenerativeAI
from src.config import settings

logger = logging.getLogger(__name__)


class GeminiLLM:
    """Wrapper for Gemini 2.5 Flash LLM"""
    
    def __init__(self):
        self.llm = ChatGoogleGenerativeAI(
            model=settings.GEMINI_MODEL,
            google_api_key=settings.GEMINI_API_KEY,
            temperature=0.3,
            max_tokens=2048,
        )
    
    def extract_invoice_text(self, invoice_text: str) -> Dict[str, Any]:
        """Extract structured data from invoice text using LLM"""
        prompt = f"""
        Analyze the following invoice text and extract structured information.
        Return a JSON object with:
        - vendor_name: extracted vendor name
        - invoice_date: extracted invoice date
        - due_date: extracted due date
        - total_amount: extracted total amount
        - currency: currency code
        - line_items: list of line items with desc, qty, unit_price, total
        - po_references: any PO numbers found
        
        Invoice text:
        {invoice_text}
        
        Return ONLY valid JSON, no additional text.
        """
        try:
            response = self.llm.invoke(prompt)
            result = json.loads(response.content)
            return result
        except Exception as e:
            logger.error(f"Error extracting invoice text: {e}")
            return {}
    
    def normalize_vendor_name(self, vendor_name: str) -> str:
        """Normalize vendor name using LLM"""
        prompt = f"""
        Normalize the following vendor name to a standard format.
        Remove extra spaces, standardize capitalization, and remove special characters where appropriate.
        Return ONLY the normalized name, no additional text.
        
        Vendor name: {vendor_name}
        """
        try:
            response = self.llm.invoke(prompt)
            return response.content.strip()
        except Exception as e:
            logger.error(f"Error normalizing vendor name: {e}")
            return vendor_name
    
    def compute_match_score(self, invoice_data: Dict[str, Any], po_data: Dict[str, Any]) -> float:
        """Compute match score between invoice and PO using LLM"""
        prompt = f"""
        Compare the following invoice and Purchase Order data.
        Return a match score between 0 and 1 based on:
        - Vendor name match
        - Amount match (within tolerance)
        - Line items match
        - PO reference match
        
        Invoice data:
        {json.dumps(invoice_data, indent=2)}
        
        PO data:
        {json.dumps(po_data, indent=2)}
        
        Return ONLY a number between 0 and 1, no additional text.
        """
        try:
            response = self.llm.invoke(prompt)
            score = float(response.content.strip())
            return max(0.0, min(1.0, score))
        except Exception as e:
            logger.error(f"Error computing match score: {e}")
            return 0.0
    
    def generate_accounting_entries(self, invoice_data: Dict[str, Any]) -> Dict[str, Any]:
        """Generate accounting entries from invoice using LLM"""
        prompt = f"""
        Generate accounting entries for the following invoice.
        Return a JSON object with:
        - entries: array of accounting entries with account_code, debit, credit, description
        - total_debits: sum of debits
        - total_credits: sum of credits
        
        Invoice data:
        {json.dumps(invoice_data, indent=2)}
        
        Return ONLY valid JSON, no additional text.
        """
        try:
            response = self.llm.invoke(prompt)
            result = json.loads(response.content)
            return result
        except Exception as e:
            logger.error(f"Error generating accounting entries: {e}")
            return {"entries": [], "total_debits": 0.0, "total_credits": 0.0}
    
    def determine_approval_status(self, invoice_amount: float, approval_threshold: float) -> str:
        """Determine approval status based on amount and rules"""
        if invoice_amount <= approval_threshold:
            return "AUTO_APPROVED"
        else:
            return "ESCALATED"


# Global LLM instance
gemini_llm = GeminiLLM()
