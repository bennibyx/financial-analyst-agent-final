# Hosting Plan

## Application

Autonomous Financial Analyst \& Earnings Call Intelligence Agent

## Backend

* Framework: FastAPI
* Container: Docker
* Local API port: 8000
* Health endpoint: /health

## AI Inference

* Provider: Nebius Token Factory
* API key: Stored privately in .env
* Base URL: To be filled from the official Nebius Token Factory documentation/console
* Model: To be selected from the available Nebius models

## Compute

* Backend does not require a GPU.
* LLM inference is intended to run through the Nebius API.

## Primary Hosting

* Provider: Nebius
* Account/credits: To be confirmed
* Instance type: To be confirmed
* Deployment details: To be confirmed

## Fallback Hosting

* Provider: Render / Railway / Fly.io
* Exact provider: To be selected if Nebius hosting is unavailable

## Secrets

* .env must never be committed.
* NEBIUS\_API\_KEY must be provided through environment/secrets configuration.

## Day 2 Validation

* Docker image builds successfully.
* docker compose up --build starts the API.
* /health returns HTTP 200.


## Day 15 v1 deployment (2026-10-12)
- Host: Render free tier, running the Docker Hub image bennibyx/financial-analyst-agent:v1
- URL: https://financial-analyst-agent-v1.onrender.com (API docs at /docs, health at /health)
- Limits: sleeps after 15 min idle (about 1 min to wake), data wiped on restart. Re-seed with scripts/seed_demo.sh <url>
- Redeploy: build and push a new image tag, then update the image in the Render dashboard
- Before judging: move to a paid always-on instance or a Nebius VM, and seed demo data on startup
