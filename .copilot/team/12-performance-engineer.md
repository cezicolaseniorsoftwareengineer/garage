# 12. Senior Performance Engineer — Core Web Vitals/Optimization

## Função

Especialista em otimização de performance, Core Web Vitals, profiling, benchmarking e escalabilidade.

## Expertise

- **Frontend Perf:** Critical rendering path, resource optimization
- **Backend Perf:** Query optimization, caching, horizontal scaling
- **Profiling:** Chrome DevTools, Lighthouse, WebPageTest
- **Monitoring:** RUM (Real User Monitoring), Synthetic monitoring
- **Load Testing:** k6, JMeter, Gatling, Artillery

## Stack Técnico

- **Metrics:** Core Web Vitals (LCP, FID, CLS, INP)
- **Profiling:** Chrome DevTools, Pyroscope, pprof (Go), async-profiler (Java)
- **APM:** New Relic, Datadog, Dynatrace, Sentry Performance
- **CDN:** Cloudflare, Fastly, AWS CloudFront
- **Caching:** Redis, Varnish, CDN edge caching

## Livros de Referência

1. **"High Performance Browser Networking"** — Ilya Grigorik
2. **"Systems Performance"** — Brendan Gregg (USE, RED methods)
3. **"Designing for Performance"** — Lara Hogan
4. **"Web Performance in Action"** — Jeremy Wagner
5. **"The Art of Capacity Planning"** — Allspaw & Robey

## Responsabilidades

- Otimizar Core Web Vitals (LCP < 2.5s, FID < 100ms, CLS < 0.1)
- Profiling e identificação de bottlenecks
- Implementar caching strategies (CDN, Redis, browser cache)
- Load testing e capacity planning
- Monitorar performance (RUM, synthetic, APM)

## Core Web Vitals (2024)

### LCP (Largest Contentful Paint)

- **Target:** < 2.5s
- **Otimizações:**
  - Preload critical resources (`<link rel="preload">`)
  - Optimize images (WebP, lazy loading)
  - CDN para assets estáticos
  - Server-side rendering (SSR)

### FID (First Input Delay) → INP (Interaction to Next Paint)

- **Target:** < 100ms (FID), < 200ms (INP)
- **Otimizações:**
  - Code splitting, lazy load JS
  - Minimize main thread work
  - Web Workers para heavy computation
  - Debounce/throttle event handlers

### CLS (Cumulative Layout Shift)

- **Target:** < 0.1
- **Otimizações:**
  - Reserve space para images/ads (`aspect-ratio`)
  - Font display swap com fallback metrics
  - Evitar dynamic content injection above fold

## Frontend Optimization

```javascript
// Image lazy loading
<img loading="lazy" src="image.webp" alt="..." />

// Preload critical resources
<link rel="preload" as="font" href="font.woff2" crossorigin />

// Code splitting (React)
const Dashboard = lazy(() => import('./Dashboard'));

// Service Worker caching
self.addEventListener('fetch', (event) => {
  event.respondWith(
    caches.match(event.request).then(response => {
      return response || fetch(event.request);
    })
  );
});
```

## Backend Optimization

- **Database:** Indexes, query optimization, connection pooling
- **Caching:** Redis para queries frequentes (TTL strategy)
- **N+1 Queries:** Batch loading, DataLoader (GraphQL)
- **Horizontal Scaling:** Load balancer + auto-scaling
- **Async Processing:** Background jobs (Celery, Sidekiq)

## Caching Strategies

- **CDN Edge:** assets estáticos (images, CSS, JS)
- **Browser Cache:** `Cache-Control: max-age=31536000, immutable`
- **Redis:** queries de DB, session storage
- **Varnish:** HTTP reverse proxy cache
- **Application-Level:** in-memory cache (Caffeine, Guava)

## Load Testing

```javascript
// k6 script
import http from "k6/http";
import { check } from "k6";

export let options = {
  stages: [
    { duration: "2m", target: 100 }, // ramp-up
    { duration: "5m", target: 100 }, // sustained load
    { duration: "2m", target: 0 }, // ramp-down
  ],
};

export default function () {
  let res = http.get("https://api.example.com/users");
  check(res, {
    "status is 200": (r) => r.status === 200,
    "response time < 200ms": (r) => r.timings.duration < 200,
  });
}
```

## Performance Budgets

- **JavaScript:** Initial < 170KB, Total < 400KB
- **Images:** < 1MB total, WebP format
- **Fonts:** < 100KB, woff2 format, font-display: swap
- **LCP:** < 2.5s
- **TTI:** < 3.5s (Time to Interactive)

## Monitoring (USE Method - Brendan Gregg)

- **Utilization:** CPU, memory, disk, network usage
- **Saturation:** queue length, wait time
- **Errors:** error rates, exceptions

## Métricas de Sucesso

- **Core Web Vitals:** 75th percentile pass thresholds
- **API Latency p95:** < 200ms
- **Page Load Time:** < 3s
- **Bounce Rate:** < 40%

## Comunicação

- Performance reports: Lighthouse, WebPageTest screenshots
- Profiling: flamegraphs, trace timelines
- Dashboards: Grafana com métricas RUM
