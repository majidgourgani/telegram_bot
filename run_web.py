"""Run the admin dashboard: ``python run_web.py``.

For production-style use, run uvicorn directly:
    uvicorn app.web.main:app --host 0.0.0.0 --port 8000
"""

import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "app.web.main:app",
        host="0.0.0.0",
        port=8000,
        reload=False,
    )
