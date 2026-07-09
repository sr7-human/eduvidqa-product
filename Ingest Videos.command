#!/bin/bash
# Double-click this file to open the EduVidQA Local Ingest app in your browser.
# It runs on your Mac (reliable) and writes to the live database.
cd "$(dirname "$0")"
exec ./.venv/bin/streamlit run tools/ingest_app.py
