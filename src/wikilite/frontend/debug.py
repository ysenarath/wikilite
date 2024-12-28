from pathlib import Path
import subprocess
import time

if __name__ == "__main__":
    app_path = Path(__file__).parent / "app.py"
    while True:
        try:
            subprocess.run(["python", str(app_path)])
        except Exception:
            time.sleep(2)
