"""
QSR (Quick Service Restaurant) Trades Configuration

This module defines the normalized trade list for fast-food restaurant construction.
"""

# NORMALIZED TRADE NAMES
# This is the master list of trades that will be used in the system
NORMALIZED_TRADES = [
    'Architecture',
    'Bathrooms',
    'Building Materials',
    'Canopies',
    'Caulking',
    'Concrete',
    'Doors & Windows',
    'Drywall',
    'Dumpster Service',
    'Earthwork',
    'Excavation',
    'Final Cleaning',
    'Flooring',
    'Framing',
    'Glasswork',
    'Landscaping',
    'Low Voltage',
    'Masonry',
    'Mechanical',
    'Metals',
    'Painting',
    'Plumbing',
    'Roofing',
    'Steel',
    'Storefront',
    'Striping',
    'TAB',
    'Toilet Accessories',
    'TPO',
    'Trusses',
    'Utilities',
    'Welding',
    'Windows'
]

# TRADE ALIASES - maps various ways people might name trades to normalized names
TRADE_ALIASES = {
    # Bathrooms
    'bathrooms': 'Bathrooms',
    'bath': 'Bathrooms',
    
    # Canopies
    'canopies': 'Canopies',
    'canopy': 'Canopies',
    
    # Caulking
    'caulking': 'Caulking',
    'sealant & caulking': 'Caulking',
    'sealant': 'Caulking',
    
    # Concrete
    'concrete': 'Concrete',
    
    # Doors & Windows
    'doors & windows': 'Doors & Windows',
    'doors': 'Doors & Windows',
    'windows': 'Doors & Windows',
    'door and window': 'Doors & Windows',
    
    # Drywall
    'drywall': 'Drywall',
    
    # Dumpster Service
    'dumpster service': 'Dumpster Service',
    'dumpster': 'Dumpster Service',
    'trash service': 'Dumpster Service',
    'dumpster services': 'Dumpster Service',
    
    # Earthwork
    'earthwork': 'Earthwork',
    'earthwork building': 'Earthwork',
    
    # Excavation
    'excavation': 'Excavation',
    
    # Final Cleaning
    'final cleaning': 'Final Cleaning',
    'post construction cleanup': 'Final Cleaning',
    'post construction cleaning': 'Final Cleaning',
    'cleaning': 'Final Cleaning',
    'cleanup': 'Final Cleaning',
    'cleanup services': 'Final Cleaning',
    'cleanup service': 'Final Cleaning',
    
    # Flooring
    'flooring': 'Flooring',
    
    # Framing
    'framing': 'Framing',
    'framing & carpentry': 'Framing',
    'carpentry': 'Framing',
    
    # Glasswork
    'glasswork': 'Glasswork',
    
    # Landscaping
    'landscaping': 'Landscaping',
    'landscape': 'Landscaping',
    
    # Low Voltage
    'low voltage': 'Low Voltage',
    
    # Masonry
    'masonry': 'Masonry',
    
    # Mechanical
    'mechanical': 'Mechanical',
    
    # Metals
    'metals': 'Metals',
    
    # Misc Steel
    'misc steel': 'Steel',
    'steel (misc)': 'Steel',
    
    # Painting
    'painting': 'Painting',
    
    # Plumbing
    'plumbing': 'Plumbing',
    
    # Roofing
    'roofing': 'Roofing',
    'tpo': 'TPO',  # Also a specific type
    
    # Steel
    'steel': 'Steel',
    
    # Storefront
    'storefront': 'Storefront',
    
    # Striping
    'striping': 'Striping',
    'striping & marking': 'Striping',
    
    # SWPPP
    'swppp': 'SWPPP',
    'swpp': 'SWPPP',
    
    # TAB
    'tab': 'TAB',
    'test and balance': 'TAB',
    'testing and balancing': 'TAB',
    
    # Toilet Accessories
    'toilet accessories': 'Toilet Accessories',
    
    # TPO
    'tpo': 'TPO',
    
    # Trusses
    'trusses': 'Trusses',
    
    # Utilities
    'utilities': 'Utilities',
    
    # Welding
    'welding': 'Welding',
}

# NOTES:
# - "Building Materials" and "Lumber" removed as they're typically supplies, not trades
# - "Storefront" kept separate as it's common in QSR
# - Various cleaning terms consolidated to "Final Cleaning"
# - Multiple steel variants consolidated appropriately
# - "Architecture" kept for design phase tracking
