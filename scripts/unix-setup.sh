#!/bin/bash
# Unix Setup Script for ACI Analysis Tool
echo "ACI Analysis Tool - Unix Setup"

# Check Python
if ! command -v python3 &> /dev/null; then
    echo "ERROR: Python 3 not found!"
    exit 1
fi

echo "Found: $(python3 --version)"

# Create virtual environment
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

# Activate and install
echo "Installing dependencies..."
source venv/bin/activate
pip install -r requirements.txt

echo "Setup complete!"
echo "Starting application..."
python app.py
