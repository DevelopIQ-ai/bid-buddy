"""
Filename parser for construction bid proposals.

Supports various filename formats and trade aliases.
"""

import re
from typing import Dict, List, Optional, Tuple
from app.utils.qsr_trades import TRADE_ALIASES

# Import QSR trade aliases from centralized configuration

# DELIMITER RULES
# Define the delimiters used to separate trades and company in filenames
TRADE_COMPANY_DELIMITER = '_'  # Separates trade from company
MULTI_TRADE_DELIMITER = ', '  # Separates multiple trades (e.g., "concrete, framing, electrical_company")
TRAILING_CHARS = [' &', '&']  # Can appear between trades (e.g., "concrete & framing_company")


def normalize_trade_name(trade_name: str) -> str:
    """
    Normalize trade name by applying aliases and standardizing format.
    
    Args:
        trade_name: Raw trade name from filename
        
    Returns:
        Normalized trade name (capitalized)
    """
    # Convert to lowercase and strip whitespace for matching
    normalized = trade_name.lower().strip()
    
    # Check for alias
    if normalized in TRADE_ALIASES:
        return TRADE_ALIASES[normalized]
    
    # Return title case (capitalize first letter of each word)
    return trade_name.strip().title()


def parse_filename(filename: str) -> Dict[str, any]:
    """
    Parse a proposal filename to extract trades and company name.
    
    Expected formats:
    - "{trade}_{company}.pdf"
    - "{trade, trade, & trade}_{company}.pdf"
    - "{trade & trade}_{company}.pdf"
    
    Args:
        filename: The full filename including extension
        
    Returns:
        Dict with:
        - trades: List of trade names (normalized)
        - company_name: Company name
        - raw_trades: Original trade string before parsing
    """
    result = {
        'trades': [],
        'company_name': None,
        'raw_trades': None,
        'error': None
    }
    
    try:
        # Remove file extension
        name_without_ext = filename.rsplit('.', 1)[0].strip()
        
        # Split on trade-company delimiter
        parts = name_without_ext.split(TRADE_COMPANY_DELIMITER, 1)
        
        if len(parts) != 2:
            result['error'] = f"Missing delimiter '{TRADE_COMPANY_DELIMITER}' in filename. Expected format '{{trade}}_{{company}}', got: {filename}"
            return result
        
        trade_part = parts[0].strip()
        company_part = parts[1].strip()
        
        result['raw_trades'] = trade_part
        result['company_name'] = company_part
        
        # Parse multiple trades
        trades = []
        
        # Remove any trailing "&" or "& " from the end
        for trailing in TRAILING_CHARS:
            trade_part = trade_part.rstrip(trailing).strip()
        
        # Split by MULTI_TRADE_DELIMITER
        trade_sections = trade_part.split(MULTI_TRADE_DELIMITER)
        
        for section in trade_sections:
            # Handle "trade & trade" format
            if '&' in section:
                # Split by "&" and process each part
                and_parts = section.split('&')
                for part in and_parts:
                    normalized = normalize_trade_name(part)
                    if normalized and normalized not in trades:
                        trades.append(normalized)
            else:
                normalized = normalize_trade_name(section)
                if normalized and normalized not in trades:
                    trades.append(normalized)
        
        result['trades'] = trades
        
        if not trades:
            result['error'] = f"Could not parse any trades from: {filename}"
        
        if not company_part:
            result['error'] = f"Could not parse company name from: {filename}"
        
    except Exception as e:
        result['error'] = f"Error parsing filename '{filename}': {str(e)}"
    
    return result


def match_trade_to_database(parsed_trades: List[str], trades_by_name: Dict[str, str]) -> Tuple[Optional[str], List[str]]:
    """
    Match parsed trades to database trades.
    
    Args:
        parsed_trades: List of normalized trade names from filename
        trades_by_name: Dict mapping trade names (lowercase) to trade IDs
        
    Returns:
        Tuple of (trade_id, unmatched_trades):
        - trade_id: The first matching trade ID, or None
        - unmatched_trades: List of trades that didn't match
    """
    matched_id = None
    unmatched = []
    
    for trade_name in parsed_trades:
        trade_lower = trade_name.lower()
        
        if trade_lower in trades_by_name:
            if not matched_id:  # Use first match
                matched_id = trades_by_name[trade_lower]
        else:
            unmatched.append(trade_name)
    
    return matched_id, unmatched


# Test function for development
if __name__ == "__main__":
    test_cases = [
        "concrete_company.pdf",
        "framing_ABC_Construction.pdf",
        "concrete, framing_company.pdf",
        "concrete, framing, & electrical_company.pdf",
        "concrete & framing_company.pdf",
        "bathrooms_company.pdf",
        "bath_company.pdf",
        "concrete framing_company.pdf",  # Should fail - no delimiter
    ]
    
    print("Testing filename parser:")
    print("=" * 80)
    for filename in test_cases:
        result = parse_filename(filename)
        print(f"\nFilename: {filename}")
        print(f"  Trades: {result['trades']}")
        print(f"  Company: {result['company_name']}")
        if result['error']:
            print(f"  Error: {result['error']}")
