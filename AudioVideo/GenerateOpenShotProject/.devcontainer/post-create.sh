#!/bin/bash

# Set default workspace folder if not provided
containerWorkspaceFolder="${containerWorkspaceFolder:-/workspace}"

echo "containerWorkspaceFolder=${containerWorkspaceFolder}"
ls -la ${containerWorkspaceFolder} || true

if [ -f "${containerWorkspaceFolder}/requirements.txt" ]; then
  pip install -r "${containerWorkspaceFolder}/requirements.txt"
else
  echo "requirements.txt not found at ${containerWorkspaceFolder}"
fi

touch ${containerWorkspaceFolder}/.bash_history