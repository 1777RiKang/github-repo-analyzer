"""Streamlit Cloud entry point — simply re-runs src/app.py."""
import os, sys, subprocess

if __name__ == "__main__":
    src_dir = os.path.join(os.path.dirname(__file__), "src")
    os.chdir(src_dir)
    subprocess.run([sys.executable, "-m", "streamlit", "run", "app.py"])
