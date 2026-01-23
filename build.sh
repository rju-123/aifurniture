#!/usr/bin/env bash
# exit on error
set -o errexit

# Install system dependencies for Pillow (if needed)
# Note: Render may not allow apt-get, so this is optional
# Uncomment if you encounter Pillow build errors
# apt-get update
# apt-get install -y \
#     libjpeg-dev \
#     zlib1g-dev \
#     libpng-dev \
#     libtiff-dev \
#     libfreetype6-dev

# Upgrade pip and install dependencies
pip install --upgrade pip setuptools wheel
pip install -r requirements.txt
