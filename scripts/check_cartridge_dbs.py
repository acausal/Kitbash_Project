#!/usr/bin/env python3
"""Check if cartridge facts.db files actually contain data."""

import sqlite3
from pathlib import Path

cartridges_dir = Path("/vercel/share/v0-project/src/cartridges")

for kbc_path in sorted(cartridges_dir.glob("*.kbc")):
    db_path = kbc_path / "facts.db"
    name = kbc_path.stem
    
    if not db_path.exists():
        print(f"{name:20s} -- NO facts.db")
        continue
    
    try:
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        
        # Check if facts table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='facts'")
        if not cursor.fetchone():
            print(f"{name:20s} -- facts table MISSING")
            conn.close()
            continue
        
        # Count rows
        cursor.execute("SELECT COUNT(*) FROM facts")
        count = cursor.fetchone()[0]
        
        # Sample a fact
        cursor.execute("SELECT id, content FROM facts LIMIT 1")
        sample = cursor.fetchone()
        
        # Check keyword index
        keyword_idx = kbc_path / "indices" / "keyword.idx"
        kw_status = "exists" if keyword_idx.exists() else "MISSING"
        
        # Check keyword index content
        kw_count = 0
        if keyword_idx.exists():
            import json
            try:
                with open(keyword_idx, 'r') as f:
                    kw_data = json.load(f)
                kw_count = len(kw_data)
            except:
                kw_count = -1  # error reading
        
        print(f"{name:20s} -- {count:3d} facts | keyword.idx: {kw_status} ({kw_count} keywords)")
        if sample:
            print(f"  {'':20s}    Sample: [{sample[0]}] {sample[1][:80]}...")
        else:
            print(f"  {'':20s}    (no data in table)")
        
        conn.close()
    except Exception as e:
        print(f"{name:20s} -- ERROR: {e}")

print()
print("=== Checking what path main.py passes to CartridgeEngine ===")
import re
main_path = Path("/vercel/share/v0-project/main.py")
content = main_path.read_text()
for match in re.finditer(r'CartridgeEngine\(([^)]*)\)', content):
    print(f"CartridgeEngine constructor call: CartridgeEngine({match.group(1)})")
