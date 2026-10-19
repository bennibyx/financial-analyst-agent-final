# Day 18 Integration Sign-off

- Date: 2026-10-19 12:47
- Hosted URL: https://financial-analyst-agent-v1.onrender.com
- Image: bennibyx/financial-analyst-agent:v5
- Result: 9/9 checks passed

| Check | Result | Seconds | Detail |
|---|---|---|---|
| GET /health (includes cold start) | PASS | 0.3 | HTTP 200 |
| GET /documents has 10-K + transcript | PASS | 0.0 | 10-K id=1, call id=2 |
| POST /extract/1 (10-K) | PASS | 18.3 | HTTP 200, 6 metrics |
| GET /documents/1/metrics | PASS | 0.3 | 6 metrics |
| POST /analyze/2 (call) | PASS | 11.1 | level=high, 4 risks |
| POST /chat (with citations) | PASS | 9.0 | HTTP 200, answer 309 chars, 3 citations |
| GET /trends | PASS | 0.3 | HTTP 200 |
| POST /brief/2 | PASS | 18.4 | HTTP 200, 7288 chars |
| GET /compare | PASS | 0.7 | HTTP 422 (422 = needs params, endpoint exists) |
