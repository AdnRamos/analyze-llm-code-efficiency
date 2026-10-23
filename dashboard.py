"""
Entry point kept for the existing Streamlit Community Cloud deployment, whose main file is `dashboard.py`.
The dashboard itself lives in dashboard/app.py (run it directly with `streamlit run dashboard/app.py`).
"""
import runpy
from pathlib import Path

runpy.run_path(str(Path(__file__).resolve().parent / "dashboard" / "app.py"), run_name="__main__")
