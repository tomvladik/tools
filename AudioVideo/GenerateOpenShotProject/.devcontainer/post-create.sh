#!/bin/bash

# Set default workspace folder if not provided
containerWorkspaceFolder="${containerWorkspaceFolder:-/workspace}"

echo "containerWorkspaceFolder=${containerWorkspaceFolder}"
ls -la ${containerWorkspaceFolder} || true

# Set up Python path for openshot
export PYTHONPATH="/usr/local/lib/python3.11/dist-packages:$PYTHONPATH"

if [ -f "${containerWorkspaceFolder}/requirements.txt" ]; then
  pip install -r "${containerWorkspaceFolder}/requirements.txt"
else
  echo "requirements.txt not found at ${containerWorkspaceFolder}"
fi

touch ${containerWorkspaceFolder}/.bash_history

# Add PYTHONPATH to bash history so it's set in shells
echo 'export PYTHONPATH="/usr/local/lib/python3.11/dist-packages:$PYTHONPATH"' >> ${containerWorkspaceFolder}/.bash_history