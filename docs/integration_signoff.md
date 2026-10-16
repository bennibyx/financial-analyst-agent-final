# Day 18 Integration Sign-off

- Date: 2026-10-16 09:10
- Hosted URL: https://financial-analyst-agent-v1.onrender.com
- Image: bennibyx/financial-analyst-agent:v5
- Result: 9/9 checks passed

| Check | Result | Seconds | Detail |
|---|---|---|---|
| GET /health (includes cold start) | PASS | 0.6 | HTTP 200 |
| GET /documents has 10-K + transcript | PASS | 0.0 | 10-K id=1, call id=2 |
| POST /extract/1 (10-K) | PASS | 17.2 | HTTP 200, 6 metrics |
| GET /documents/1/metrics | PASS | 0.3 | 6 metrics |
| POST /analyze/2 (call) | PASS | 11.0 | level=medium, 2 risks |
| POST /chat (with citations) | PASS | 7.1 | HTTP 200, answer 304 chars, 3 citations |
| GET /trends | PASS | 0.3 | HTTP 200 |
| POST /brief/2 | PASS | 15.6 | HTTP 200, 9066 chars |
| GET /compare | PASS | 0.3 | HTTP 422 (422 = needs params, endpoint exists) |
