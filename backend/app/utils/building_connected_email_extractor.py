import re
import logging
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)


class BuildingConnectedEmailExtractor:
    """Simple extractor for BuildingConnected email data - no web scraping"""
    
    @staticmethod
    def extract_project_name(subject: str) -> Optional[str]:
        """
        Extract project name from email subject
        
        Expected format: "Proposal Submitted - {project_name}"
        """
        if subject.startswith("Proposal Submitted - "):
            return subject.replace("Proposal Submitted - ", "").strip()
        return None
    
    @staticmethod
    def extract_proposal_links(html_content: str) -> List[str]:
        """
        Extract download links from BuildingConnected email HTML
        
        Returns list of proposal download links
        """
        # Find all links containing /download/ (BuildingConnected proposal links)
        download_links = re.findall(r'href="([^"]*\/download\/[^"]*)"', html_content)
        return download_links
    
    @staticmethod
    def extract_company_and_trade(html_content: str, text_content: str = "") -> Dict[str, Optional[str]]:
        """
        Extract company name and trade from email content
        
        Returns dict with 'company_name' and 'trade' keys
        """
        result = {
            "company_name": None,
            "trade": None
        }
        
        # Try to extract from HTML first
        # BuildingConnected emails often have structured data
        
        # Pattern for company name (often in strong tags or specific divs)
        company_patterns = [
            r'<strong>([^<]+)</strong>\s+has submitted',
            r'Subcontractor:\s*<[^>]+>([^<]+)<',
            r'Company:\s*<[^>]+>([^<]+)<',
            r'from\s+<strong>([^<]+)</strong>',
        ]
        
        for pattern in company_patterns:
            match = re.search(pattern, html_content, re.IGNORECASE)
            if match:
                result["company_name"] = match.group(1).strip()
                break
        
        # Pattern for trade/scope
        trade_patterns = [
            r'Trade:\s*<[^>]+>([^<]+)<',
            r'Scope:\s*<[^>]+>([^<]+)<',
            r'for\s+(?:the\s+)?([^<]+)\s+scope',
            r'Category:\s*<[^>]+>([^<]+)<',
        ]
        
        for pattern in trade_patterns:
            match = re.search(pattern, html_content, re.IGNORECASE)
            if match:
                result["trade"] = match.group(1).strip()
                break
        
        # Fallback to text content if HTML parsing didn't work
        if not result["company_name"] and text_content:
            # Try text patterns
            text_company_patterns = [
                r'(\w+(?:\s+\w+)*)\s+has submitted',
                r'Subcontractor:\s*(\w+(?:\s+\w+)*)',
                r'Company:\s*(\w+(?:\s+\w+)*)',
            ]
            
            for pattern in text_company_patterns:
                match = re.search(pattern, text_content, re.IGNORECASE)
                if match:
                    result["company_name"] = match.group(1).strip()
                    break
        
        if not result["trade"] and text_content:
            text_trade_patterns = [
                r'Trade:\s*(\w+(?:\s+\w+)*)',
                r'Scope:\s*(\w+(?:\s+\w+)*)',
                r'Category:\s*(\w+(?:\s+\w+)*)',
            ]
            
            for pattern in text_trade_patterns:
                match = re.search(pattern, text_content, re.IGNORECASE)
                if match:
                    result["trade"] = match.group(1).strip()
                    break
        
        return result
    
    @staticmethod
    def process_buildingconnected_email(email_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract all relevant data from a BuildingConnected email
        
        Args:
            email_data: Email data with subject, html, text fields
            
        Returns:
            Dict with extracted information
        """
        subject = email_data.get("subject", "")
        html_content = email_data.get("html", "")
        text_content = email_data.get("text", "")
        
        # Extract project name
        project_name = BuildingConnectedEmailExtractor.extract_project_name(subject)
        
        # Extract proposal links
        proposal_links = BuildingConnectedEmailExtractor.extract_proposal_links(html_content)
        
        # Extract company and trade info
        company_trade_info = BuildingConnectedEmailExtractor.extract_company_and_trade(
            html_content, 
            text_content
        )
        
        result = {
            "success": True,
            "project_name": project_name,
            "company_name": company_trade_info["company_name"],
            "trade": company_trade_info["trade"],
            "proposal_links": proposal_links,
            "link_count": len(proposal_links),
            "source": "BuildingConnected Email"
        }
        
        # Log what we extracted
        logger.info(f"Extracted BuildingConnected data: project={project_name}, "
                   f"company={company_trade_info['company_name']}, "
                   f"trade={company_trade_info['trade']}, "
                   f"links={len(proposal_links)}")
        
        return result


def should_process_buildingconnected(email_data: Dict[str, Any]) -> bool:
    """
    Check if an email should be processed as a BuildingConnected email
    
    Args:
        email_data: The email webhook data
        
    Returns:
        True if email should be processed, False otherwise
    """
    from_email = email_data.get("from_", "").lower()
    subject = email_data.get("subject", "")
    
    # Check if from contains buildingconnected.com
    return (
        "buildingconnected.com" in from_email and
        subject.startswith("Proposal Submitted")
    )