# ============================================================
# tests/unit/test_logrotate.py — Tests de rotación de logs
# ------------------------------------------------------------
import sys
import tempfile
import gzip
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import atlas_logrotate as lr

def test_rotate_logs_creates_gz():
    with tempfile.TemporaryDirectory() as tmpdir:
        log_dir = Path(tmpdir) / "logs"
        log_dir.mkdir()
        
        # Crear log viejo
        old_log = log_dir / "test_old.log"
        old_log.write_text("log antiguo\n")
        # Forzar mtime antiguo
        import os, time
        old_time = time.time() - (10 * 86400)  # 10 días
        os.utime(old_log, (old_time, old_time))
        
        # Crear log nuevo
        new_log = log_dir / "test_new.log"
        new_log.write_text("log nuevo\n")
        
        # Ejecutar rotación
        rotated, compressed, removed = lr.rotate_logs(days=7, dry_run=False, log_dir=log_dir)
        
        # Verificar
        gz_files = list(log_dir.glob("*.gz"))
        assert len(gz_files) == 1
        assert "test_old" in gz_files[0].name
        
        # Verificar que el nuevo sigue ahí
        assert new_log.exists()
        assert not old_log.exists()
        
        # Verificar contenido del .gz
        with gzip.open(gz_files[0], 'rt') as f:
            content = f.read()
        assert content == "log antiguo\n"

def test_errors_jsonl_trim():
    with tempfile.TemporaryDirectory() as tmpdir:
        log_dir = Path(tmpdir) / "logs"
        log_dir.mkdir()
        
        errors_file = log_dir / "errors.jsonl"
        # 15000 líneas
        lines = [f'{{"timestamp": "2026-01-01T00:00:00", "msg": "error {i}"}}' for i in range(15000)]
        errors_file.write_text('\n'.join(lines) + '\n')
        
        rotated, compressed, removed = lr.rotate_logs(days=7, dry_run=False, log_dir=log_dir)
        
        # Debe quedar 10000
        remaining = errors_file.read_text().splitlines()
        assert len(remaining) == 10000
        assert removed == 5000

def test_dry_run_does_not_modify():
    with tempfile.TemporaryDirectory() as tmpdir:
        log_dir = Path(tmpdir) / "logs"
        log_dir.mkdir()
        
        old_log = log_dir / "test_old.log"
        old_log.write_text("log antiguo\n")
        import os, time
        old_time = time.time() - (10 * 86400)
        os.utime(old_log, (old_time, old_time))
        
        rotated, compressed, removed = lr.rotate_logs(days=7, dry_run=True, log_dir=log_dir)
        
        # En dry-run no debe modificar
        assert old_log.exists()
        assert rotated == 1
        assert compressed == 1

if __name__ == "__main__":
    test_rotate_logs_creates_gz()
    test_errors_jsonl_trim()
    test_dry_run_does_not_modify()
    print("✅ tests/unit/test_logrotate.py: OK")