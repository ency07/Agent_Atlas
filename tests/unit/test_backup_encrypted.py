# ============================================================
# tests/unit/test_backup_encrypted.py — Tests de backup cifrado
# ------------------------------------------------------------
import sys
import tempfile
import tarfile
import shutil
import io
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import atlas_backup_encrypted as ab

def test_create_and_list_backups():
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        # Clonar memory_data reducido para test
        test_data = tmp / "memory_data"
        test_data.mkdir()
        (test_data / "state").mkdir()
        (test_data / "state" / "daemon.heartbeat").write_text('{"pid": 1, "last_tick": "2026-01-01T00:00:00"}')
        (test_data / "vault").mkdir()
        (test_data / "vault" / "global").mkdir()
        (test_data / "vault" / "global" / "MEMORY.md").write_text("# memoria de test")

        # Backup con recipient dummy (no cifra de verdad, solo tarball si falla age)
        backup_dir = tmp / "backups"
        backup_dir.mkdir()
        timestamp = "20260101_000000"
        tar_path = backup_dir / f"atlas_backup_{timestamp}.tar.gz"
        enc_path = backup_dir / f"atlas_backup_{timestamp}.tar.gz.age"

        # Probar create_tarball
        ab.create_tarball(test_data, tar_path)
        assert tar_path.exists()
        assert tar_path.stat().st_size > 0

        # Probar list_backups
        backups = ab.list_backups(backup_dir)
        assert len(backups) == 0  # sin .age, no se listan

        # Crear .age vacío y listar
        enc_path.write_bytes(b"fake-age")
        backups = ab.list_backups(backup_dir)
        assert len(backups) == 1
        assert backups[0]["file"] == enc_path

def test_cleanup_old_backups():
    with tempfile.TemporaryDirectory() as tmpdir:
        backup_dir = Path(tmpdir) / "backups"
        backup_dir.mkdir()

        # Crear 5 backups .age falsos
        for i in range(5):
            ts = f"2026010{i+1}_000000"
            (backup_dir / f"atlas_backup_{ts}.tar.gz.age").write_bytes(b"x")

        # Mantener 2
        ab.cleanup_old_backups(backup_dir, keep=2)
        remaining = list(backup_dir.glob("*.age"))
        assert len(remaining) == 2

def test_extract_tarball():
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        src = tmp / "src"
        src.mkdir()
        (src / "hello.txt").write_text("contenido de prueba")

        tar_path = tmp / "test.tar.gz"
        ab.create_tarball(src, tar_path)

        out = tmp / "out"
        out.mkdir()
        ab.extract_tarball(tar_path, out)

        extracted = out / "src" / "hello.txt"
        assert extracted.exists()
        assert extracted.read_text() == "contenido de prueba"

if __name__ == "__main__":
    test_create_and_list_backups()
    test_cleanup_old_backups()
    test_extract_tarball()
    print("OK tests/unit/test_backup_encrypted.py")