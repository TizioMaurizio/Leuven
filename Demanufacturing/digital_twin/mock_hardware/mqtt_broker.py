"""
mock_hardware/mqtt_broker.py

Starts a local Mosquitto MQTT broker as a subprocess.

ARCHITECTURAL CONSTRAINT:
- This module MUST NOT import from core/, io/, or viz/
- Requires 'mosquitto' to be installed and available on PATH
- Used only for local research simulation convenience
"""

import subprocess
import time
import shutil
import os
import tempfile
import socket
from pathlib import Path


class EmbeddedBroker:
    """
    Starts a local Mosquitto MQTT broker as a subprocess.

    Notes:
    - Requires 'mosquitto' to be installed and available on PATH.
    - This is NOT an in-process Python broker.
    - Used only for local research simulation convenience.
    """

    def __init__(self, port: int = 1883):
        self.port = port
        self.process = None
        self.config_file = None

    def _create_config_file(self, port: int) -> Path:
        """
        Create a temporary Mosquitto config file with anonymous access enabled.
        This is required for Mosquitto 2.0+ which disables anonymous access by default.
        
        Returns:
            Path: Path to the temporary config file.
        """
        config_content = f"""# Temporary Mosquitto config for simulation
    listener {port}
    allow_anonymous true
    """
        # Create temp file that persists
        fd, path = tempfile.mkstemp(suffix='.conf', text=True)
        with os.fdopen(fd, 'w') as f:
            f.write(config_content)
        return Path(path)

    def _find_mosquitto(self) -> str | None:
        """
        Find mosquitto executable on PATH or in common Windows installation locations.
        
        Returns:
            str: Path to mosquitto executable, or None if not found.
        """
        # First check PATH
        mosquitto_path = shutil.which("mosquitto")
        if mosquitto_path:
            return mosquitto_path
        
        # Check common Windows installation paths
        if os.name == 'nt':  # Windows
            common_paths = [
                r"C:\Program Files\mosquitto\mosquitto.exe",
                r"C:\Program Files (x86)\mosquitto\mosquitto.exe",
            ]
            for path in common_paths:
                if Path(path).exists():
                    return path
        
        return None

    def start(self) -> bool:
        """
        Start the Mosquitto broker subprocess.
        
        Returns:
            bool: True if broker started successfully, False otherwise.
        """
        # Find mosquitto executable
        mosquitto_path = self._find_mosquitto()
        
        if not mosquitto_path:
            print("❌ Mosquitto not found on system PATH.")
            print("   Install Mosquitto: https://mosquitto.org/download/")
            return False

        max_port_tries = 8
        base_port = int(self.port)

        for attempt in range(max_port_tries):
            try_port = base_port + attempt
            try:
                # Create config file for this try_port
                cfg = self._create_config_file(try_port)
                proc = subprocess.Popen(
                    [mosquitto_path, "-c", str(cfg)],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True
                )

                # Wait briefly and probe the listening port
                started = False
                for _ in range(10):
                    if proc.poll() is not None:
                        break
                    try:
                        with socket.create_connection(("127.0.0.1", try_port), timeout=0.5):
                            started = True
                            break
                    except Exception:
                        time.sleep(0.2)

                if started and proc.poll() is None:
                    # Success
                    self.process = proc
                    self.config_file = cfg
                    self.port = try_port
                    print(f"✓ MQTT broker running on port {self.port}")
                    return True
                else:
                    # Failed to start/listen on this port; capture stderr for diagnostics
                    try:
                        _, stderr = proc.communicate(timeout=1)
                    except Exception:
                        stderr = None
                    try:
                        proc.terminate()
                        proc.wait(timeout=1)
                    except Exception:
                        try:
                            proc.kill()
                        except Exception:
                            pass
                    # Cleanup config file
                    try:
                        if cfg and Path(cfg).exists():
                            Path(cfg).unlink()
                    except Exception:
                        pass
                    if stderr:
                        print(f"   Mosquitto stderr: {stderr.strip()}")
                    # try next port
                    continue

            except FileNotFoundError:
                print("❌ Mosquitto not found on system PATH.")
                return False
            except PermissionError:
                print(f"❌ Permission denied starting Mosquitto on port {try_port}")
                return False
            except Exception as e:
                print(f"❌ Failed to start broker on port {try_port}: {e}")
                continue

        print(f"❌ Unable to start Mosquitto on ports {base_port}-{base_port+max_port_tries-1}")
        return False

    def stop(self):
        """Stop the Mosquitto broker subprocess and clean up config file."""
        if self.process:
            try:
                self.process.terminate()
                self.process.wait(timeout=5)
                print("✓ MQTT broker stopped")
            except subprocess.TimeoutExpired:
                self.process.kill()
                print("⚠️ MQTT broker forcefully killed")
            finally:
                self.process = None
        
        # Clean up config file
        if self.config_file and self.config_file.exists():
            try:
                self.config_file.unlink()
            except Exception:
                pass  # Ignore cleanup errors

    def is_running(self) -> bool:
        """Check if the broker process is still running."""
        return self.process is not None and self.process.poll() is None

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()
        return False
