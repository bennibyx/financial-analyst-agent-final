# Deploy runbook (owner: Bhavana)
1. Pull main and confirm tests pass: python scripts/contract_test.py
2. Build and push: docker buildx build --platform linux/amd64 -t bennibyx/financial-analyst-agent:vN -f backend/Dockerfile --push .
3. Render: set the image tag to vN and redeploy.
4. Re-seed demo docs: bash scripts/seed_demo.sh https://financial-analyst-agent-v1.onrender.com
5. Check: curl <url>/health, then python scripts/eval_chat.py
Never put API keys in the repo; the Nebius key is an environment variable on Render.
