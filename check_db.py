import sqlite3
conn = sqlite3.connect('E:/Agente_IA/memory_data/state/memory.db')
conn.row_factory = sqlite3.Row

tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
for t in tables:
    name = t['name']
    print(f'\n=== TABLE: {name} ===')
    cols = conn.execute(f'PRAGMA table_info({name})').fetchall()
    for c in cols:
        print(f'  {c["name"]} {c["type"]} {"PK" if c["pk"] else ""}')
    
    cnt = conn.execute(f'SELECT COUNT(*) as c FROM {name}').fetchone()['c']
    print(f'  ROWS: {cnt}')
    
    sample = conn.execute(f'SELECT * FROM {name} LIMIT 2').fetchall()
    for r in sample:
        print(f'  SAMPLE: {dict(r)}')
conn.close()