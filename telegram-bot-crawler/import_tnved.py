#!/usr/bin/env python3
"""
Import TNVED data from scraped JSON into the bot database.
Usage: python import_tnved.py <json_file>

Expected JSON format:
[
  {"code": "6204530000", "description": "Юбки женские...", "duty_pct": 12.0, "vat_pct": 20.0},
  ...
]
"""

import json
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from app.storage.db import Database


def import_tnved(json_path: str, db_url: str = "sqlite:///data.db"):
    """Import TNVED codes from JSON file into database."""
    
    print(f"Loading data from {json_path}...")
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    print(f"Found {len(data)} items")
    
    # Initialize database
    db = Database(db_url)
    db.initialize()
    
    # Check if table exists, create if not
    db.execute('''
        CREATE TABLE IF NOT EXISTS tnved_codes (
            code TEXT PRIMARY KEY,
            description TEXT,
            duty_pct REAL,
            vat_pct REAL,
            excise TEXT,
            gr31 TEXT,
            licensing TEXT,
            certification TEXT,
            extra TEXT
        )
    ''')
    
    imported = 0
    skipped = 0
    errors = 0
    
    for item in data:
        code = str(item.get('code', '')).strip()
        
        # Skip non-10-digit codes (not leaf nodes)
        if len(code) != 10 or not code.isdigit():
            skipped += 1
            continue
        
        description = item.get('description') or item.get('desc', '')
        duty_pct = float(item.get('duty_pct', item.get('duty', 0)) or 0)
        vat_pct = float(item.get('vat_pct', 20.0) or 20.0)
        
        try:
            # Check if exists
            existing = db.fetchone("SELECT code FROM tnved_codes WHERE code = ?", (code,))
            
            if existing:
                # Update
                db.execute('''
                    UPDATE tnved_codes 
                    SET description = ?, duty_pct = ?, vat_pct = ?
                    WHERE code = ?
                ''', (description, duty_pct, vat_pct, code))
            else:
                # Insert
                db.execute('''
                    INSERT INTO tnved_codes (code, description, duty_pct, vat_pct)
                    VALUES (?, ?, ?, ?)
                ''', (code, description, duty_pct, vat_pct))
            
            imported += 1
            
            if imported % 1000 == 0:
                print(f"  Imported {imported} codes...")
                
        except Exception as e:
            print(f"  Error importing {code}: {e}")
            errors += 1
    
    print(f"\nDone!")
    print(f"  Imported: {imported}")
    print(f"  Skipped (non-10-digit): {skipped}")
    print(f"  Errors: {errors}")
    
    # Show sample
    sample = db.fetchone("SELECT code, description, duty_pct FROM tnved_codes LIMIT 1")
    if sample:
        print(f"\nSample record: {sample}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python import_tnved.py <json_file>")
        print("Example: python import_tnved.py tnved_alta.json")
        sys.exit(1)
    
    import_tnved(sys.argv[1])
