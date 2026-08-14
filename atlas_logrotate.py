# ============================================================
# atlas_logrotate.py — Rotación de logs para Atlas
# ------------------------------------------------------------
# - Mantiene últimos N días (default 7)
# - Comprime logs rotados (.gz)
# - Limpia errors.jsonl (mantiene últimas 10000 líneas)
# - Se ejecuta diariamente via Task Scheduler
#
# Uso: python atlas_logrotate.py [--days 7] [--dry-run]
# ============================================================
import os
import sys
import gzip
import shutil
import argparse
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).parent
DEFAULT_LOG_DIR = ROOT / "logs"
STATE_DIR = ROOT / "memory_data" / "state"

def rotate_logs(days=7, dry_run=False, log_dir=None):
    """Rota logs en LOG_DIR"""
    log_dir = log_dir or DEFAULT_LOG_DIR
    if not log_dir.exists():
        print(f"[{datetime.now().isoformat()}] Log dir no existe: {log_dir}")
        return
    
    cutoff = datetime.now() - timedelta(days=days)
    rotated = 0
    compressed = 0
    removed = 0
    
    for log_file in log_dir.glob("*.log"):
        # Saltar archivos ya comprimidos
        if log_file.suffix == ".gz":
            continue
        
        # Obtener fecha de modificación
        mtime = datetime.fromtimestamp(log_file.stat().st_mtime)
        
        if mtime < cutoff:
            # Rotar: renombrar con timestamp y comprimir
            timestamp = mtime.strftime("%Y%m%d")
            rotated_name = log_dir / f"{log_file.stem}_{timestamp}.log"
            compressed_name = log_dir / f"{log_file.stem}_{timestamp}.log.gz"
            
            if not dry_run:
                # Renombrar
                log_file.rename(rotated_name)
                # Comprimir
                with open(rotated_name, 'rb') as f_in:
                    with gzip.open(compressed_name, 'wb') as f_out:
                        shutil.copyfileobj(f_in, f_out)
                # Eliminar rotado sin comprimir
                rotated_name.unlink()
            else:
                print(f"[DRY-RUN] Rotaría: {log_file.name} -> {compressed_name.name}")
            
            rotated += 1
            compressed += 1
            print(f"[{datetime.now().isoformat()}] Rotado: {log_file.name} -> {compressed_name.name}")
    
    # Limpiar errors.jsonl (mantener últimas 10000 líneas)
    errors_file = log_dir / "errors.jsonl"
    if errors_file.exists():
        try:
            lines = errors_file.read_text(encoding='utf-8', errors='ignore').splitlines()
            if len(lines) > 10000:
                if not dry_run:
                    errors_file.write_text('\n'.join(lines[-10000:]) + '\n', encoding='utf-8')
                removed = len(lines) - 10000
                print(f"[{datetime.now().isoformat()}] errors.jsonl: eliminadas {removed} líneas antiguas")
        except Exception as e:
            print(f"[{datetime.now().isoformat()}] Error limpiando errors.jsonl: {e}")
    
    # Limpiar .gz muy antiguos (> 30 días)
    cutoff_old = datetime.now() - timedelta(days=30)
    for gz_file in log_dir.glob("*.log.gz"):
        mtime = datetime.fromtimestamp(gz_file.stat().st_mtime)
        if mtime < cutoff_old:
            if not dry_run:
                gz_file.unlink()
            print(f"[{datetime.now().isoformat()}] Eliminado .gz antiguo: {gz_file.name}")
    
    return rotated, compressed, removed

def main():
    parser = argparse.ArgumentParser(description="Rotación de logs Atlas")
    parser.add_argument("--days", type=int, default=7, help="Días a mantener (default 7)")
    parser.add_argument("--dry-run", action="store_true", help="Solo simular")
    args = parser.parse_args()
    
    log_dir = DEFAULT_LOG_DIR
    print(f"[{datetime.now().isoformat()}] === INICIO ROTACIÓN LOGS ===")
    print(f"[{datetime.now().isoformat()}] Directorio: {log_dir}")
    print(f"[{datetime.now().isoformat()}] Mantener: {args.days} días")
    
    try:
        rotated, compressed, removed = rotate_logs(args.days, args.dry_run, log_dir)
        print(f"[{datetime.now().isoformat()}] === FIN: rotados={rotated}, comprimidos={compressed}, líneas_eliminadas={removed} ===")
    except Exception as e:
        print(f"[{datetime.now().isoformat()}] ERROR: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()