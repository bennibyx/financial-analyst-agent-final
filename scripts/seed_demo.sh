#!/bin/bash
# usage: scripts/seed_demo.sh https://financial-analyst-agent-v1.onrender.com
URL=${1:?usage: scripts/seed_demo.sh https://your-app.onrender.com}
for f in data/sample/nvidia_Q4FY26_10K.pdf data/sample/nvidia_Q4FY26_call.pdf; do
  echo "uploading $f"; curl -s -F "file=@$f" "$URL/upload"; echo
done
