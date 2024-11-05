#!/bin/bash
source $(dirname $(readlink -f "$0"))/.venv/bin/activate
python app.py
