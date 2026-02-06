import sqlite3
import pandas as pd
import re
import os

DB_PATH = "data.db"
FILES = {
    "decl": "7706406291-declaredproducts-.csv",
    "cert": "7706406291-productcommoncertification-.csv"
}

def clean_code(code_str):
    if pd.isna(code_str):
        return []
    # Remove "из" prefix
    code_str = str(code_str).replace("из ", "").replace("Код ТН ВЭД ", "").strip()
    
    # Split by comma or semicolon
    parts = re.split(r'[;,]', code_str)
    cleaned = []
    for p in parts:
        # Keep only digits
        digits = re.sub(r'\D', '', p)
        if len(digits) >= 2: # At least 2 digits to make sense
            cleaned.append(digits)
    return cleaned

def run_import():
    print("Starting import...")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Create table
    cursor.execute("DROP TABLE IF EXISTS certification_rules")
    cursor.execute("""
        CREATE TABLE certification_rules (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tnved_prefix TEXT,
            product_name TEXT,
            doc_type TEXT, -- 'declaration' or 'certificate'
            standard_doc TEXT,
            source_file TEXT
        )
    """)
    cursor.execute("CREATE INDEX idx_cert_prefix ON certification_rules(tnved_prefix)")
    
    total_rows = 0
    
    # 1. Process Declaration List
    f_decl = FILES["decl"]
    if os.path.exists(f_decl):
        print(f"Processing {f_decl}...")
        try:
            df = pd.read_csv(f_decl, encoding='cp1251', sep=';')
            # Columns: 'Наименование продукции' (idx 2), 'Идентификация...' (idx 3)
            # Or use names if possible
            col_name = 'Наименование продукции'
            col_code = 'Идентификация продукции по коду ТН ВЭД ЕАЭС'
            col_doc = 'Документы по стандартизации, устанавливающие требования к продукции'
            
            for _, row in df.iterrows():
                name = row.get(col_name, "")
                code_raw = row.get(col_code, "")
                doc = row.get(col_doc, "")
                
                codes = clean_code(code_raw)
                for c in codes:
                    cursor.execute("""
                        INSERT INTO certification_rules (tnved_prefix, product_name, doc_type, standard_doc, source_file)
                        VALUES (?, ?, ?, ?, ?)
                    """, (c, name, 'Декларация', doc, f_decl))
                    total_rows += 1
                    
        except Exception as e:
            print(f"Error processing {f_decl}: {e}")
            
    # 2. Process Certificate List
    f_cert = FILES["cert"]
    if os.path.exists(f_cert):
        print(f"Processing {f_cert}...")
        try:
            df = pd.read_csv(f_cert, encoding='cp1251', sep=';')
            # Columns: 'Наименование продукции' (idx 1), 'Идентификация...' (idx 2)
            # Find exact column name for name (might have typo)
            col_name = None
            for c in df.columns:
                if 'Наименование' in c:
                    col_name = c
                    break
            col_code = 'Идентификация продукции по коду ТН ВЭД ЕАЭС'
            col_doc = None
            for c in df.columns:
                if 'Документы' in c and 'требования' in c:
                    col_doc = c
                    break

            for _, row in df.iterrows():
                name = row.get(col_name, "") if col_name else ""
                code_raw = row.get(col_code, "")
                doc = row.get(col_doc, "") if col_doc else ""
                
                codes = clean_code(code_raw)
                for c in codes:
                    cursor.execute("""
                        INSERT INTO certification_rules (tnved_prefix, product_name, doc_type, standard_doc, source_file)
                        VALUES (?, ?, ?, ?, ?)
                    """, (c, name, 'Сертификат', doc, f_cert))
                    total_rows += 1
                    
        except Exception as e:
            print(f"Error processing {f_cert}: {e}")
            
    conn.commit()
    conn.close()
    print(f"Done! Imported {total_rows} rules.")

if __name__ == "__main__":
    run_import()
