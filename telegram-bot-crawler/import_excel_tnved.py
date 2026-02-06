# Import TNVED data from TWS Excel file
# v3: Fixed column mapping based on analysis

import pandas as pd
import numpy as np
import sqlite3
import sys
from pathlib import Path

EXCEL_FILE = "TWS_TNVED_2026-02-06.xlsx"
DB_FILE = "data.db"

def main():
    print(f"Reading {EXCEL_FILE}...")
    
    # Read second sheet (ТНВЭД)
    xl = pd.ExcelFile(EXCEL_FILE)
    df = xl.parse(xl.sheet_names[1])
    
    print(f"Found {len(df)} rows")
    
    # Known column mapping from analysis:
    # Col 0 = Код (9-digit, need to pad to 10)
    # Col 1 = Наименование (description)
    # Col 2 = Тариф (duty, e.g. "5%")
    # Col 3 = Подробности (ignore)
    
    import_to_db(df, code_col=0, desc_col=1, duty_col=2)

def import_to_db(df, code_col, desc_col, duty_col):
    """Import data into SQLite."""
    
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    # Create table if not exists
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS tnved_codes (
            code TEXT PRIMARY KEY,
            description TEXT,
            duty_pct REAL,
            vat_pct REAL DEFAULT 0.2,
            source TEXT DEFAULT 'tws_excel'
        )
    """)
    
    inserted = 0
    skipped = 0
    
    cols = df.columns.tolist()
    
    for idx, row in df.iterrows():
        try:
            # Get code and convert to string
            raw_code = row[cols[code_col]]
            if pd.isna(raw_code):
                skipped += 1
                continue
                
            # Handle int64/float types (including numpy)
            if isinstance(raw_code, (int, float, np.integer, np.floating)):
                code = str(int(raw_code))
            else:
                code = str(raw_code)
            
            code = code.strip().replace(" ", "").replace(".", "")
            
            # Pad to 10 digits with leading zeros
            code = code.zfill(10)
            
            # Skip non-10-digit codes
            if len(code) != 10 or not code.isdigit():
                skipped += 1
                continue
            
            # Description
            desc = str(row[cols[desc_col]]) if pd.notna(row[cols[desc_col]]) else ""
            # Clean up arrows
            desc = desc.replace("🠺", "→").replace(" 🠺 ", " → ")
            
            # Parse duty (e.g. "5%", "0%", "10%")
            duty_pct = 0.1  # Default 10%
            if pd.notna(row[cols[duty_col]]):
                duty_raw = str(row[cols[duty_col]])
                duty_raw = duty_raw.replace("%", "").replace(",", ".").strip()
                try:
                    duty_pct = float(duty_raw) / 100.0  # Convert to decimal
                except:
                    duty_pct = 0.1
            
            # Upsert
            cursor.execute("""
                INSERT INTO tnved_codes (code, description, duty_pct, source)
                VALUES (?, ?, ?, 'tws_excel')
                ON CONFLICT(code) DO UPDATE SET
                    description = excluded.description,
                    duty_pct = excluded.duty_pct,
                    source = 'tws_excel'
            """, (code, desc, duty_pct))
            
            inserted += 1
            
            if inserted % 1000 == 0:
                print(f"  Processed {inserted} codes...")
                
        except Exception as e:
            if skipped < 5:
                print(f"Error on row {idx}: {e}")
            skipped += 1
    
    conn.commit()
    conn.close()
    
    print(f"\n=== Import complete ===")
    print(f"Inserted/Updated: {inserted}")
    print(f"Skipped: {skipped}")
    print(f"\nDatabase: {DB_FILE}")

if __name__ == "__main__":
    main()
