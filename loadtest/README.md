# Load tests

k6 profiles. Not run in CI — they need a populated database and a machine that
is not also running the build, and a load test on a noisy box produces numbers
that are worse than none.

```bash
# Mint a read key in the studio (Settings → API keys), then:
k6 run -e BASE=http://localhost:8003 -e API_KEY=ia_live_... loadtest/public-api.js
```

## What the thresholds mean

`p(95)<300` on article detail is the number to watch. It is the request a
reader waits on, and it is the one that regresses when a serializer picks up an
unguarded relation — the classic N+1 that is invisible in development with
three articles and obvious here with three thousand.

The sitemap threshold is deliberately loose (1.5s) and included anyway: it
scans the most rows of anything in the system, and no reader ever waits on it,
which is exactly why it is the endpoint that quietly gets slower for years.
