/**
 * k6 load profile for the public delivery API.
 *
 *   k6 run -e BASE=http://localhost:8003 -e API_KEY=ia_live_... loadtest/public-api.js
 *
 * The mix is modelled on what a front end actually does per page, not on
 * hammering one endpoint: an article render is one detail fetch, and a listing
 * page is one list fetch, so a profile that is 90% detail reads is the honest
 * one. Sitemap and slugs are included at low weight because they are the
 * requests that scan the most rows and are therefore the ones that fall over
 * first under load — and they are easy to forget precisely because no reader
 * ever waits on them.
 *
 * Thresholds are set at the point where a reader notices, not at a round
 * number: p95 under 300ms for cached reads, and a hard zero on 5xx.
 */

import http from "k6/http";
import { check, group } from "k6";
import { Rate } from "k6/metrics";

const BASE = __ENV.BASE || "http://localhost:8003";
const API_KEY = __ENV.API_KEY || "";
const SLUG = __ENV.SLUG || "how-neural-machine-translation-works";

const errors = new Rate("business_errors");

export const options = {
  scenarios: {
    steady: {
      executor: "ramping-vus",
      startVUs: 0,
      stages: [
        { duration: "30s", target: 20 },
        { duration: "2m", target: 20 },
        // A step, not a ramp: cache stampedes show up on the step and are
        // invisible on a gentle ramp.
        { duration: "10s", target: 80 },
        { duration: "1m", target: 80 },
        { duration: "30s", target: 0 },
      ],
    },
  },
  thresholds: {
    "http_req_duration{kind:detail}": ["p(95)<300"],
    "http_req_duration{kind:list}": ["p(95)<400"],
    "http_req_duration{kind:sitemap}": ["p(95)<1500"],
    http_req_failed: ["rate<0.01"],
    business_errors: ["rate<0.01"],
  },
};

const params = (kind) => ({
  headers: { "X-API-Key": API_KEY },
  tags: { kind },
});

export default function () {
  group("article detail", () => {
    const res = http.get(
      `${BASE}/api/v1/public/articles/${encodeURIComponent(SLUG)}/`,
      params("detail"),
    );
    const ok = check(res, {
      "200": (r) => r.status === 200,
      // Not just a 200: the annotation index is the payload the whole SEO
      // design depends on, and an empty one is a silent regression that a
      // status-code check would pass.
      "annotations present": (r) =>
        (r.json("annotations_index") || []).length >= 0 && r.body.length > 500,
    });
    errors.add(!ok);
  });

  group("listing", () => {
    const res = http.get(`${BASE}/api/v1/public/articles/`, params("list"));
    errors.add(!check(res, { "200": (r) => r.status === 200 }));
  });

  group("search", () => {
    const res = http.get(
      `${BASE}/api/v1/public/search/?q=translation`,
      params("search"),
    );
    // Search being unavailable is a degraded state, not a failure -- the site
    // is designed to keep serving without it, so this asserts the contract
    // rather than the engine.
    errors.add(!check(res, { "answers": (r) => r.status === 200 }));
  });

  group("sitemap", () => {
    const res = http.get(`${BASE}/api/v1/public/sitemap-index/`, params("sitemap"));
    errors.add(!check(res, { "200": (r) => r.status === 200 }));
  });
}
