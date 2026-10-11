import os
import threading
import time
from collections import defaultdict, deque

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

LIMITED = ("/ask", "/extract/", "/analyze/", "/chat")


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, per_minute=None):
        super().__init__(app)
        self.limit = int(per_minute or os.getenv("RATE_LIMIT_PER_MIN", "20"))
        self.hits = defaultdict(deque)
        self.lock = threading.Lock()

    async def dispatch(self, request, call_next):
        if request.method == "POST" and request.url.path.startswith(LIMITED):
            fwd = request.headers.get("x-forwarded-for", "")
            client = fwd.split(",")[0].strip() or (request.client.host if request.client else "unknown")
            now = time.monotonic()
            with self.lock:
                q = self.hits[client]
                while q and now - q[0] > 60:
                    q.popleft()
                if len(q) >= self.limit:
                    retry = int(60 - (now - q[0])) + 1
                    return JSONResponse(
                        status_code=429,
                        headers={"Retry-After": str(retry)},
                        content={"error": {"code": "rate_limited",
                                           "message": f"Too many requests. Try again in {retry} seconds."}},
                    )
                q.append(now)
        return await call_next(request)
