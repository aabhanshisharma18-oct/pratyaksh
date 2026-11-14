from __future__ import annotations
import os,subprocess,sys
from pathlib import Path
from .samples.generate import generate

def main():
    generate();print("D2 samples and evaluation report generated.");print("Open http://127.0.0.1:8000/d2");env={**os.environ,"PRATYAKSH_DEMO_IDENTITY":os.getenv("PRATYAKSH_DEMO_IDENTITY","Demo examiner (self-declared)")};subprocess.run([sys.executable,"-m","uvicorn","main:app","--host","127.0.0.1","--port","8000"],cwd=Path(__file__).parents[1],env=env,check=True)
if __name__=="__main__":main()
