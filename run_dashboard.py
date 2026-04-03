import subprocess
import sys

def main():
    try:
        subprocess.run(["streamlit", "run", "interface/dashboard.py"])
    except KeyboardInterrupt:
        print("\nShutting down dashboard...")
        sys.exit(0)

if __name__ == "__main__":
    main()