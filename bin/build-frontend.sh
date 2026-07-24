#!/bin/bash
# Build script for Render static site

# Replace API_URL in frontend
if [ -n "$API_URL" ]; then
    sed -i "s|window.API_URL|'$API_URL'|g" frontend/index.html
fi

echo "Frontend build complete"
