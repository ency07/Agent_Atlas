#!/usr/bin/env python3
"""
voice_bridge.py — Integracion de voz para AEGIS-JARVIS.

Componentes:
  1. STT: Whisper (local) via Ollama o API directa.
  2. TTS: Piper (local, bilingue ES/EN).
  3. Wake word: Doble palmada via sounddevice + numpy.
  4. Bridge: Envia transcripcion al backend /execute.

Flujo:
  Doble palmada -> Activar microfono -> Whisper transcribe -> Enviar a /execute -> Piper lee respuesta

Uso:
  python voice_bridge.py                          # Modo interactivo (clap-to-talk)
  python voice_bridge.py --listen                 # Escucha continua
  python voice_bridge.py --tts "texto a decir"   # TTS directo
  python voice_bridge.py --stt                   # STT una vez
  python voice_bridge.py --health                # Verifica componentes

Requisitos:
  pip install sounddevice numpy requests
  # Para Whisper: instalar whisper localmente o usar Ollama
  # Para Piper: descargar binario de piper-tts
"""

import sys
import os
import time
import json
import tempfile
import wave
import struct
import subprocess
import threading
from pathlib import Path

# --- Config ---
BACKEND_URL = os.environ.get("AEGIS_BACKEND_URL", "http://127.0.0.1:8765")
WHISPER_MODEL = os.environ.get("WHISPER_MODEL", "base")
PIPER_VOICE = os.environ.get("PIPER_VOICE", "es_ES/davefx-medium")
CLAP_THRESHOLD = float(os.environ.get("CLAP_THRESHOLD", "0.6"))
CLAP_COOLDOWN = 2.0
SAMPLE_RATE = 16000
RECORD_SECONDS = 8
LANGUAGE = os.environ.get("VOICE_LANG", "es")

# Parse args
_ARGS = sys.argv[1:]


def _check_imports():
    """Verifica que las dependencias esten instaladas."""
    missing = []
    try:
        import sounddevice
    except ImportError:
        missing.append("sounddevice")
    try:
        import numpy
    except ImportError:
        missing.append("numpy")
    try:
        import requests
    except ImportError:
        missing.append("requests")
    if missing:
        print("[voice] Faltan dependencias: {}".format(", ".join(missing)))
        print("[voice] Ejecuta: pip install " + " ".join(missing))
        sys.exit(1)


# ============================================================
#  CLAP DETECTOR
# ============================================================

class ClapDetector:
    """Detecta doble palmada usando picos de energia de audio."""

    def __init__(self, threshold=CLAP_THRESHOLD, cooldown=CLAP_COOLDOWN):
        self.threshold = threshold
        self.cooldown = cooldown
        self._last_clap = 0
        self._first_clap = 0
        self._listening = False
        self._stream = None
        self._callback = None

    def on_clap(self, callback):
        """Registra callback para cuando se detecta doble palmada."""
        self._callback = callback

    def start(self):
        """Inicia la escucha de audio."""
        import sounddevice as sd
        import numpy as np

        self._listening = True
        self._stream = sd.InputStream(
            channels=1, samplerate=SAMPLE_RATE, blocksize=1600,
            callback=self._audio_callback
        )
        self._stream.start()
        print("[clap] Escuchando palmadas (threshold={:.2f})...".format(self.threshold))

    def stop(self):
        """Detiene la escucha."""
        self._listening = False
        if self._stream:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception:
                pass

    def _audio_callback(self, indata, frames, time_info, status):
        import numpy as np
        if not self._listening:
            return
        try:
            energy = float(np.sqrt(np.mean(indata.astype(float) ** 2)))
            now = time.time()

            if energy > self.threshold:
                if now - self._last_clap > self.cooldown:
                    if now - self._first_clap < 0.8 and self._first_clap > 0:
                        self._first_clap = 0
                        self._last_clap = now
                        print("\n[clap] DOBLE PALMADA DETECTADA!")
                        if self._callback:
                            self._callback()
                    else:
                        self._first_clap = now
        except Exception:
            pass


# ============================================================
#  STT — Whisper (local via Ollama or whisper CLI)
# ============================================================

def stt_whisper(audio_path=None):
    """Transcribe audio usando Whisper.

    Opciones (en orden de preferencia):
      1. whisper CLI local (pip install openai-whisper)
      2. Ollama con modelo whisper
      3. Grabar audio del microfono y transcribir

    Returns:
        str: Texto transcrito.
    """
    import sounddevice as sd
    import numpy as np

    # Si no se da audio, grabar del microfono
    if audio_path is None:
        print("[stt] Grabando {} segundos de audio...".format(RECORD_SECONDS))
        audio = sd.rec(int(RECORD_SECONDS * SAMPLE_RATE), samplerate=SAMPLE_RATE, channels=1, dtype='float32')
        sd.wait()
        print("[stt] Grabacion completada.")

        # Guardar como WAV temporal
        tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        audio_path = tmp.name
        tmp.close()

        # Convertir float32 a int16
        audio_int16 = (audio * 32767).astype(np.int16)
        with wave.open(audio_path, 'wb') as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(SAMPLE_RATE)
            wf.writeframes(audio_int16.tobytes())

    print("[stt] Transcribiendo con Whisper...")

    # Opcion 1: whisper CLI
    try:
        result = subprocess.run(
            ["whisper", audio_path, "--language", LANGUAGE, "--model", WHISPER_MODEL,
             "--output_format", "txt", "--output_dir", tempfile.gettempdir()],
            capture_output=True, text=True, timeout=30
        )
        if result.returncode == 0:
            txt_file = Path(tempfile.gettempdir()) / (Path(audio_path).stem + ".txt")
            if txt_file.exists():
                text = txt_file.read_text(encoding="utf-8").strip()
                print("[stt] Whisper texto: {}".format(text[:100]))
                # Cleanup
                try:
                    os.unlink(audio_path)
                    txt_file.unlink()
                except Exception:
                    pass
                return text
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    # Opcion 2: intentar con python whisper
    try:
        import whisper
        model = whisper.load_model(WHISPER_MODEL)
        result = model.transcribe(audio_path, language=LANGUAGE)
        text = result.get("text", "").strip()
        print("[stt] Whisper texto: {}".format(text[:100]))
        try:
            os.unlink(audio_path)
        except Exception:
            pass
        return text
    except ImportError:
        pass
    except Exception as e:
        print("[stt] Error whisper python: {}".format(e))

    # Fallback: no se pudo transcribir
    print("[stt] Whisper no disponible. Instala: pip install openai-whisper")
    try:
        os.unlink(audio_path)
    except Exception:
        pass
    return ""


# ============================================================
#  TTS — Piper (local)
# ============================================================

def tts_piper(text, output_path=None):
    """Sintetiza voz usando Piper TTS (local).

    Piper debe estar instalado como binario o via pip.
    Si no esta disponible, usa fallback a system TTS.

    Args:
        text: Texto a sintetizar.
        output_path: Ruta del archivo WAV de salida.

    Returns:
        str: Ruta del archivo WAV generado, o None si fallo.
    """
    if not text.strip():
        return None

    if output_path is None:
        tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        output_path = tmp.name
        tmp.close()

    print("[tts] Sintetizando: '{}'".format(text[:60]))

    # Opcion 1: piper CLI
    try:
        result = subprocess.run(
            ["piper", "--model", PIPER_VOICE, "--output_file", output_path],
            input=text.encode("utf-8"),
            capture_output=True, timeout=15
        )
        if result.returncode == 0 and Path(output_path).exists():
            print("[tts] Piper OK: {}".format(output_path))
            return output_path
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    # Opcion 2: piper python
    try:
        from piper import PiperVoice
        voice = PiperVoice.load(PIPER_VOICE)
        with wave.open(output_path, 'wb') as wf:
            voice.synthesize(text, wf)
        print("[tts] Piper python OK: {}".format(output_path))
        return output_path
    except (ImportError, Exception):
        pass

    # Fallback: es-speak (Windows)
    try:
        # Intentar conPowerShell SAPI
        ps_cmd = (
            'Add-Type -AssemblyName System.Speech; '
            '$s = New-Object System.Speech.Synthesis.SpeechSynthesizer; '
            '$s.Speak("{}")'.format(text.replace('"', '\\"'))
        )
        subprocess.run(["powershell", "-Command", ps_cmd], capture_output=True, timeout=10)
        print("[tts] Usado fallback Windows SAPI")
        return None
    except Exception:
        pass

    print("[tts] Piper no disponible. Instala: pip install piper-tts")
    return None


def play_audio(path):
    """Reproduce un archivo de audio WAV."""
    if not path or not Path(path).exists():
        return

    # Opcion 1: sounddevice
    try:
        import sounddevice as sd
        import soundfile as sf
        data, sr = sf.read(path)
        sd.play(data, sr)
        sd.wait()
        return
    except ImportError:
        pass

    # Opcion 2: winsound (Windows)
    try:
        import winsound
        winsound.PlaySound(path, winsound.SND_FILENAME)
        return
    except (ImportError, Exception):
        pass

    # Opcion 3: subprocess aplay/afplay
    try:
        if sys.platform == "win32":
            subprocess.run(["start", "", path], shell=True, timeout=10)
        elif sys.platform == "darwin":
            subprocess.run(["afplay", path], timeout=10)
        else:
            subprocess.run(["aplay", path], timeout=10)
    except Exception:
        pass

    # Cleanup
    try:
        os.unlink(path)
    except Exception:
        pass


# ============================================================
#  BACKEND INTEGRATION
# ============================================================

def send_to_backend(prompt, mode="chat"):
    """Envia un prompt al backend /execute y devuelve la respuesta.

    Args:
        prompt: Texto del usuario.
        mode: 'chat' o 'agent'.

    Returns:
        dict con la respuesta del backend.
    """
    import requests

    try:
        resp = requests.post(
            f"{BACKEND_URL}/execute",
            json={"prompt": prompt, "force_mode": mode},
            timeout=60
        )
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        print("[backend] Error: {}".format(e))
        return {"error": str(e)}


# ============================================================
#  FULL PIPELINE
# ============================================================

def voice_pipeline():
    """Pipeline completo: clap -> record -> transcribe -> execute -> speak."""
    print("\n[voice] Pipeline de voz activo.")
    print("[voice] Haz una DOBLE PALMADA para activar el microfono.")
    print("[voice] Presiona Ctrl+C para salir.\n")

    def on_clap():
        """Callback de doble palmada."""
        print("\n[voice] Microfono activado. Habla ahora...")

        # 1. Transcribir
        text = stt_whisper()
        if not text:
            print("[voice] No se detecto voz. Intenta de nuevo.")
            return

        print("[voice] Texto: {}".format(text))

        # 2. Enviar al backend
        print("[voice] Enviando a Atlas...")
        result = send_to_backend(text)
        response = result.get("response", "")
        if result.get("error"):
            response = "Error: " + result["error"]

        print("[voice] Respuesta: {}".format(response[:200]))

        # 3. Leer respuesta
        if response:
            print("[voice] Leyendo respuesta...")
            wav = tts_piper(response)
            if wav:
                play_audio(wav)

    # Iniciar detector de palmadas
    detector = ClapDetector()
    detector.on_clap(on_clap)
    detector.start()

    try:
        while True:
            time.sleep(0.5)
    except KeyboardInterrupt:
        print("\n[voice] Deteniendo...")
        detector.stop()
        print("[voice] Listo.")


# ============================================================
#  CLI
# ============================================================

def health_check():
    """Verifica que los componentes de voz esten disponibles."""
    print("=== Voice Bridge Health ===\n")

    # sounddevice
    try:
        import sounddevice as sd
        devices = sd.query_devices()
        input_devs = [d for d in devices if d.get('max_input_channels', 0) > 0]
        print("[OK] sounddevice: {} dispositivos de entrada".format(len(input_devs)))
        if input_devs:
            default = sd.query_devices(kind='input')
            print("     Default input: {}".format(default.get('name', '?')))
    except Exception as e:
        print("[FAIL] sounddevice: {}".format(e))

    # numpy
    try:
        import numpy
        print("[OK] numpy: {}".format(numpy.__version__))
    except ImportError:
        print("[FAIL] numpy no instalado")

    # whisper
    try:
        import whisper
        print("[OK] whisper: disponible (modelo {})".format(WHISPER_MODEL))
    except ImportError:
        # Check CLI
        try:
            result = subprocess.run(["whisper", "--help"], capture_output=True, timeout=5)
            print("[OK] whisper CLI: disponible")
        except Exception:
            print("[WARN] whisper: no instalado. pip install openai-whisper")

    # piper
    try:
        from piper import PiperVoice
        print("[OK] piper: disponible (voz {})".format(PIPER_VOICE))
    except ImportError:
        try:
            result = subprocess.run(["piper", "--help"], capture_output=True, timeout=5)
            print("[OK] piper CLI: disponible")
        except Exception:
            print("[WARN] piper: no instalado. Ver https://github.com/rhasspy/piper")

    # Backend
    try:
        import requests
        resp = requests.get(f"{BACKEND_URL}/health", timeout=3)
        if resp.status_code == 200:
            d = resp.json()
            print("[OK] Backend: {} ({})".format(BACKEND_URL, d.get("status", "?")))
        else:
            print("[WARN] Backend: HTTP {}".format(resp.status_code))
    except Exception as e:
        print("[FAIL] Backend: {}".format(e))

    print("\n=== Config ===")
    print("  Backend URL: {}".format(BACKEND_URL))
    print("  Whisper model: {}".format(WHISPER_MODEL))
    print("  Piper voice: {}".format(PIPER_VOICE))
    print("  Clap threshold: {}".format(CLAP_THRESHOLD))
    print("  Language: {}".format(LANGUAGE))


def main():
    _check_imports()

    if "--health" in _ARGS:
        health_check()
        return

    if "--tts" in _ARGS:
        idx = _ARGS.index("--tts")
        text = _ARGS[idx + 1] if idx + 1 < len(_ARGS) else "Hola, soy Atlas."
        wav = tts_piper(text)
        if wav:
            play_audio(wav)
        return

    if "--stt" in _ARGS:
        text = stt_whisper()
        print("Transcripcion: {}".format(text))
        return

    if "--listen" in _ARGS:
        print("[voice] Modo escucha continua (sin clap). Ctrl+C para salir.")
        while True:
            try:
                text = stt_whisper()
                if text:
                    print("[voice] Texto: {}".format(text))
                    result = send_to_backend(text)
                    resp = result.get("response", "")
                    print("[voice] Atlas: {}".format(resp[:200]))
                    if resp:
                        wav = tts_piper(resp)
                        if wav:
                            play_audio(wav)
            except KeyboardInterrupt:
                break
            except Exception as e:
                print("[voice] Error: {}".format(e))
        return

    # Default: clap-to-talk pipeline
    voice_pipeline()


if __name__ == "__main__":
    main()
