# ============================================================
# atlas_backup_encrypted.py — Backup cifrado de la bóveda Atlas
# ------------------------------------------------------------
# - Crea tarball de memory_data/
# - Lo cifra con age (API directa, evita problemas encoding CLI)
# - Sube a destino remoto (GitHub privado, disco externo, S3, etc.)
# - Mantiene últimos N backups (default 14)
# - Verifica integridad al restaurar
#
# Uso:
#   python atlas_backup_encrypted.py backup --recipient age1... --out-dir /backup
#   python atlas_backup_encrypted.py decrypt --backup-file backup.age --identity AGE-SECRET-KEY-... --restore-to memory_data_restore
#   python atlas_backup_encrypted.py list --out-dir /backup
#   python atlas_backup_encrypted.py generate
# ============================================================
import sys
import tarfile
import argparse
import io
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).parent
MEMORY_ROOT = ROOT / "memory_data"
DEFAULT_BACKUP_DIR = ROOT / "backups_encrypted"
AGE_KEY_DIR = ROOT / ".age_keys"

# Import age API
from age.file import Encryptor, Decryptor
from age.keyloader import resolve_public_key, load_keys_txt


def age_encrypt(input_file, output_file, recipient):
    """Cifra archivo con age usando API directa"""
    recipient_obj = resolve_public_key(recipient)[0]
    
    with open(input_file, 'rb') as f_in:
        data = f_in.read()
    
    output = io.BytesIO()
    with Encryptor([recipient_obj], output) as encryptor:
        encryptor.write(data)
    
    with open(output_file, 'wb') as f_out:
        f_out.write(output.getvalue())
    return True


def age_decrypt(input_file, output_file, identity_file):
    """Descifra archivo con age usando API directa"""
    # Cargar claves privadas
    keys = []
    with open(identity_file, 'r') as f:
        for line in f:
            line = line.strip()
            if line:
                keys.extend(load_keys_txt(identity_file))
                break
    
    if not keys:
        raise RuntimeError("No se pudo cargar clave privada")
    
    with open(input_file, 'rb') as f_in:
        with Decryptor(keys, f_in) as decryptor:
            data = decryptor.read()
    
    with open(output_file, 'wb') as f_out:
        f_out.write(data)
    return True


def age_generate():
    """Genera par de claves age usando CLI (no hay API directa)"""
    import subprocess
    import sys
    
    cmd = [sys.executable, "-m", "age.cli", "generate"]
    result = subprocess.run(
        cmd, capture_output=True, text=True,
        encoding='utf-8', errors='replace'
    )
    if result.returncode != 0:
        raise RuntimeError(f"age generate falló: {result.stderr}")
    
    # Parsear salida (la clave pública va a stderr, el resto a stdout)
    output = (result.stdout or "") + (result.stderr or "")
    lines = output.strip().split('\n')
    public_key = None
    private_key = None
    for line in lines:
        line = line.strip()
        if line.startswith("Public key: "):
            public_key = line.replace("Public key: ", "").strip()
        elif line.startswith("AGE-SECRET-KEY-"):
            private_key = line.strip()
    if not public_key or not private_key:
        raise RuntimeError(f"No se pudo parsear salida de age generate: {output}")
    return public_key, private_key

def create_tarball(source_dir, output_file):
    """Crea tarball comprimido del directorio"""
    with tarfile.open(output_file, "w:gz") as tar:
        tar.add(source_dir, arcname=source_dir.name)
    return True

def extract_tarball(input_file, output_dir):
    """Extrae tarball"""
    with tarfile.open(input_file, "r:gz") as tar:
        tar.extractall(output_dir)
    return True

def list_backups(backup_dir):
    """Lista backups disponibles"""
    backup_dir = Path(backup_dir)
    if not backup_dir.exists():
        return []
    backups = []
    for f in backup_dir.glob("atlas_backup_*.tar.gz.age"):
        try:
            # Formato: atlas_backup_YYYYMMDD_HHMMSS.tar.gz.age
            name = f.stem.replace("atlas_backup_", "").replace(".tar.gz", "")
            dt = datetime.strptime(name, "%Y%m%d_%H%M%S")
            backups.append({"file": f, "datetime": dt, "size": f.stat().st_size})
        except Exception:
            continue
    return sorted(backups, key=lambda x: x["datetime"], reverse=True)

def cleanup_old_backups(backup_dir, keep=14):
    """Elimina backups antiguos manteniendo solo los últimos N"""
    backups = list_backups(backup_dir)
    for b in backups[keep:]:
        b["file"].unlink()
        print(f"Eliminado backup antiguo: {b['file'].name}")

def backup_cmd(args):
    """Comando backup: cifra y guarda"""
    backup_dir = Path(args.out_dir)
    backup_dir.mkdir(parents=True, exist_ok=True)
    
    # Verificar recipient
    if not args.recipient.startswith("age1"):
        raise ValueError("Recipient debe ser una clave pública age (age1...)")
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    tar_name = f"atlas_backup_{timestamp}.tar.gz"
    enc_name = f"{tar_name}.age"
    
    tar_path = backup_dir / tar_name
    enc_path = backup_dir / enc_name
    
    print(f"[{datetime.now().isoformat()}] Creando backup: {enc_name}")
    
    # 1. Crear tarball
    print("  Creando tarball...")
    create_tarball(MEMORY_ROOT, tar_path)
    print(f"  Tamaño: {tar_path.stat().st_size / 1024 / 1024:.1f} MB")
    
    # 2. Cifrar
    print("  Cifrando con age...")
    age_encrypt(tar_path, enc_path, args.recipient)
    print(f"  Cifrado: {enc_path.stat().st_size / 1024 / 1024:.1f} MB")
    
    # 3. Eliminar tarball temporal
    tar_path.unlink()
    
    # 4. Limpiar antiguos
    if args.keep > 0:
        cleanup_old_backups(backup_dir, args.keep)
    
    print(f"[OK] Backup completado: {enc_name}")
    return enc_path

def decrypt_cmd(args):
    """Comando decrypt: descifra y extrae"""
    backup_dir = Path(args.out_dir)
    enc_path = backup_dir / args.backup_file
    
    if not enc_path.exists():
        raise FileNotFoundError(f"Backup no encontrado: {enc_path}")
    
    identity_file = Path(args.identity_file)
    if not identity_file.exists():
        raise FileNotFoundError(f"Archivo de identidad no encontrado: {identity_file}")
    
    restore_dir = Path(args.restore_to)
    if restore_dir.exists():
        raise FileExistsError(f"Directorio de destino ya existe: {restore_dir}")
    
    print(f"[{datetime.now().isoformat()}] Restaurando: {args.backup_file}")
    
    # 1. Descifrar
    print("  Descifrando...")
    tar_path = backup_dir / args.backup_file.replace(".age", "")
    age_decrypt(enc_path, tar_path, identity_file)
    
    # 2. Extraer
    print("  Extrayendo...")
    extract_tarball(tar_path, restore_dir.parent)
    
    # 3. Limpiar tarball temporal
    tar_path.unlink()
    
    print(f"[OK] Restaurado en: {restore_dir}")
    return restore_dir

def list_cmd(args):
    """Lista backups"""
    backup_dir = Path(args.out_dir)
    backups = list_backups(backup_dir)
    if not backups:
        print("No hay backups")
        return
    for b in backups:
        size_mb = b["size"] / 1024 / 1024
        print(f"  {b['datetime'].strftime('%Y-%m-%d %H:%M:%S')}  {b['file'].name}  ({size_mb:.1f} MB)")

def generate_keys_cmd(args):
    """Genera par de claves age"""
    AGE_KEY_DIR.mkdir(parents=True, exist_ok=True)
    public_key, private_key = age_generate()
    
    pub_file = AGE_KEY_DIR / "public_key.txt"
    priv_file = AGE_KEY_DIR / "private_key.txt"
    
    pub_file.write_text(public_key)
    priv_file.write_text(private_key)
    
    print(f"Clave pública:  {public_key}")
    print(f"Clave privada:  (guardada en {priv_file})")
    print(f"Guarda la clave privada en lugar seguro!")
    print(f"Para backups usa: --recipient {public_key}")
    print(f"Para restaurar usa: --identity {priv_file}")

def main():
    parser = argparse.ArgumentParser(description="Backup cifrado Atlas (age)")
    subparsers = parser.add_subparsers(dest="command", required=True)
    
    # backup
    p_backup = subparsers.add_parser("backup", help="Crear backup cifrado")
    p_backup.add_argument("--recipient", required=True, help="Clave pública age (age1...)")
    p_backup.add_argument("--out-dir", default=DEFAULT_BACKUP_DIR, help="Directorio destino")
    p_backup.add_argument("--keep", type=int, default=14, help="Backups a mantener (default 14)")
    
    # decrypt
    p_decrypt = subparsers.add_parser("decrypt", help="Restaurar backup")
    p_decrypt.add_argument("--backup-file", required=True, help="Archivo .age a restaurar")
    p_decrypt.add_argument("--identity", required=True, dest="identity_file", help="Archivo clave privada (AGE-SECRET-KEY...)")
    p_decrypt.add_argument("--restore-to", required=True, help="Directorio destino (ej: memory_data_restore)")
    p_decrypt.add_argument("--out-dir", default=DEFAULT_BACKUP_DIR, help="Directorio donde están los backups")
    
    # list
    p_list = subparsers.add_parser("list", help="Listar backups")
    p_list.add_argument("--out-dir", default=DEFAULT_BACKUP_DIR, help="Directorio de backups")
    
    # generate
    p_gen = subparsers.add_parser("generate", help="Generar par de claves age")
    
    args = parser.parse_args()
    
    try:
        if args.command == "backup":
            backup_cmd(args)
        elif args.command == "decrypt":
            decrypt_cmd(args)
        elif args.command == "list":
            list_cmd(args)
        elif args.command == "generate":
            generate_keys_cmd(args)
    except Exception as e:
        print(f"ERROR: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()