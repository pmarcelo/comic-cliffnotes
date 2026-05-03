import subprocess
import sys
import os

def main():
    mode = os.getenv("CLIFFNOTES_MODE", "").upper()
    app = "app_reader.py" if mode == "ONLINE" else "app_admin.py"

    try:
        subprocess.run(["streamlit", "run", app])
    except KeyboardInterrupt:
        print("\nShutting down dashboard...")
        sys.exit(0)

if __name__ == "__main__":
    main()
