# Observability

This document describes the platform's observability architecture: logs, metrics, traces, and distributed tracing.

## Overview

The platform implements OpenTelemetry-based observability with:
- **Logs:** Structured JSON logging with correlation IDs
- **Metrics:** Prometheus-compatible metrics with OpenMetrics format
- **Traces:** Distributed traces with context propagation
- **Correlation:** Unified correlation across all signals

## Architecture

```
┌─────────────┐
│ Application │
└──────┬──────┘
       │ (OTLP)
       ↓
┌──────────────────┐
│ OTel Collector   │ ← Batching, sampling, enrichment
└──────┬───────────┘
       │
       ├─→ Prometheus (metrics)
       ├─→ Loki (logs)
       └─→ Tempo/Jaeger (traces)
```

## OpenTelemetry Instrumentation

### SDK Initialization

**Python (FastAPI):**
```python
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

# Initialize tracer provider
provider = TracerProvider(
    resource=Resource.create(
        {
            "service.name": "demo-api",
            "service.version": "1.0.0",
            "deployment.environment": "production",
        }
    )
)

# Configure OTLP exporter
otlp_exporter = OTLPSpanExporter(
    endpoint="http://otel-collector:4317",
    insecure=True,
)

provider.add_span_processor(BatchSpanProcessor(otlp_exporter))
trace.set_tracer_provider(provider)

# Auto-instrument FastAPI
FastAPIInstrumentor.instrument_app(app)
```

**TypeScript (Next.js):**
```typescript
import { NodeSDK } from '@opentelemetry/sdk-node';
import { OTLPTraceExporter } from '@opentelemetry/exporter-trace-otlp-grpc';
import { Resource } from '@opentelemetry/resources';

const sdk = new NodeSDK({
  resource: new Resource({
    'service.name': 'demo-web',
    'service.version': '1.0.0',
  }),
  traceExporter: new OTLPTraceExporter({
    url: 'http://otel-collector:4317',
  }),
});

sdk.start();
```

### Resource Attributes

All services include these standard resource attributes:
- `service.name`: Service identifier
- `service.version`: Deployment version
- `service.namespace`: Kubernetes namespace
- `deployment.environment`: dev/staging/production
- `k8s.pod.name`: Pod name (injected by collector)
- `k8s.node.name`: Node name (injected by collector)

## Structured Logging

### Log Format

All logs are JSON-structured with mandatory fields:

```json
{
  "timestamp": "2026-09-21T10:30:45.123Z",
  "level": "INFO",
  "logger": "demo-api.handlers",
  "message": "Request processed",
  "correlation_id": "req-abc123",
  "trace_id": "4bf92f3577b34da6a3ce929d0e0e4736",
  "span_id": "00f067aa0ba902b7",
  "service": "demo-api",
  "environment": "production",
  "user_id": "user-456",
  "request_path": "/api/users",
  "request_method": "GET",
  "status_code": 200,
  "duration_ms": 45
}
```

### Correlation ID Propagation

Request correlation IDs are:
1. Generated at ingress (or accepted from client via `X-Correlation-ID` header)
2. Propagated via HTTP headers and trace context
3. Included in all logs, metrics labels, and trace metadata
4. Returned to client in response headers

**Header:** `X-Correlation-ID`

### Log Levels

- **DEBUG:** Detailed diagnostic information (not in production)
- **INFO:** Informational messages (normal operation)
- **WARNING:** Warning messages (degraded but operational)
- **ERROR:** Error messages (failed operation, retry possible)
- **CRITICAL:** Critical failures (service unavailable)

### Sensitive Data Handling

Never log:
- Passwords or secrets
- API keys or tokens
- Full credit card numbers
- Personally identifiable information (PII) without masking
- Session tokens

Use redaction for sensitive fields:
```python
logger.info("User login", user_id=user_id, email="***@example.com")
```

## Error Tracking (Sentry)

Error tracking is opt-in and configured entirely from the deployment environment; no DSN or project
key is ever committed:

| Variable | Purpose | Default |
| --- | --- | --- |
| `SENTRY_DSN` | Project DSN reported to when the service opts in | unset (tracking off) |
| `SENTRY_ENVIRONMENT` | Environment label attached to every event | service's `environment` argument |

```python
configure_logging(
    level=os.getenv("LOG_LEVEL", "INFO"),
    service_name="incident-api",
    environment=os.getenv("ENVIRONMENT", "development"),
    enable_sentry=os.getenv("SENTRY_DSN") is not None,
)
```

Guarantees enforced in `packages/observability/logging_config.py`:

- **Opt-in:** a DSN in the environment alone does not start reporting; `enable_sentry` must be true
  (or a DSN passed explicitly), so a stray variable cannot begin shipping telemetry.
- **No PII:** `send_default_pii=False`, and `Authorization`, `Cookie` and `X-API-Key` request
  headers are redacted before an event is sent.
- **No noisy alerts:** `ValidationError` and `HTTPException` are dropped as control flow, not
  defects.
- **No key leakage:** only the DSN host is logged, never the project key embedded in the DSN.
- **Sampling:** 10% of traces and profiles in production, 100% elsewhere.
- **Fail-open:** an uninstalled or misconfigured SDK logs a warning/error but never blocks startup.

`SENTRY_DSN` and `SENTRY_ENVIRONMENT` are defined in `.env.example`; deployments must supply them
through their secret store or platform environment.

## Metrics

### Metric Types

**Counter:** Monotonically increasing values
```python
http_requests_total{method="GET", path="/api/users", status="200"}
```

**Gauge:** Current state values
```python
active_connections{service="demo-api"}
```

**Histogram:** Distribution of values
```python
http_request_duration_seconds_bucket{le="0.1"}
```

**Summary:** Similar to histogram with percentiles calculated client-side

### Standard Metrics

#### HTTP Metrics

```
# Request count
http_requests_total{method, path, status}

# Request duration
http_request_duration_seconds{method, path}

# Request size
http_request_size_bytes{method, path}

# Response size
http_response_size_bytes{method, path}

# Active requests
http_requests_in_flight{method, path}
```

#### Application Metrics

```
# Database queries
db_queries_total{operation, table, status}
db_query_duration_seconds{operation, table}

# Redis operations
redis_operations_total{operation, status}
redis_operation_duration_seconds{operation}

# Queue metrics
queue_jobs_total{queue, status}
queue_job_duration_seconds{queue}
queue_depth{queue}
```

#### AI Agent Metrics

```
# Agent executions
agent_executions_total{agent_type, outcome}
agent_execution_duration_seconds{agent_type}
agent_confidence{agent_type}

# LLM operations
llm_requests_total{provider, model, outcome}
llm_request_duration_seconds{provider, model}
llm_tokens_consumed{provider, model, type="prompt|completion"}
llm_cost_dollars{provider, model}
```

#### SRE Metrics

```
# SLI metrics (see 16-sre-slos.md)
sli:availability:ratio_rate1h
sli:latency:p99_5m
slo:error_budget_burn_rate:1h
```

### Cardinality Management

Avoid high-cardinality labels:
- ❌ **Bad:** User IDs, request IDs, trace IDs
- ✅ **Good:** Service name, environment, status code ranges

Use recording rules to pre-aggregate high-resolution metrics.

## Distributed Tracing

### Trace Context Propagation

The platform uses W3C Trace Context for propagation:

**Headers:**
- `traceparent`: `00-{trace-id}-{span-id}-{flags}`
- `tracestate`: Vendor-specific context

**Example:**
```
traceparent: 00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01
```

### Span Attributes

Standard span attributes:
- `http.method`: HTTP method
- `http.url`: Full URL
- `http.status_code`: Response status
- `http.user_agent`: Client user agent
- `db.system`: Database system (postgresql, redis)
- `db.statement`: SQL statement (sanitized)
- `db.operation`: Operation type
- `messaging.system`: Queue system
- `error`: Boolean indicating error
- `error.type`: Error type/class
- `error.message`: Error message

### Sampling

**Strategy:** Head-based sampling at collector

- **Production:** 10% sampling (all errors sampled)
- **Staging:** 50% sampling
- **Development:** 100% sampling

**Configuration:**
```yaml
# otel-collector-config.yaml
processors:
  probabilistic_sampler:
    sampling_percentage: 10
    hash_seed: 42
```

### Trace Storage

- **Retention:** 7 days for all traces
- **Backend:** Tempo or Jaeger
- **Query:** Via Grafana UI

## OpenTelemetry Collector

### Pipeline Configuration

```yaml
receivers:
  otlp:
    protocols:
      grpc:
        endpoint: 0.0.0.0:4317
      http:
        endpoint: 0.0.0.0:4318

processors:
  batch:
    timeout: 10s
    send_batch_size: 1024
  
  memory_limiter:
    check_interval: 1s
    limit_mib: 512
  
  resource:
    attributes:
      - key: k8s.cluster.name
        value: production-cluster
        action: insert

exporters:
  prometheus:
    endpoint: 0.0.0.0:8889
    namespace: app
  
  loki:
    endpoint: http://loki:3100/loki/api/v1/push
  
  otlp/tempo:
    endpoint: tempo:4317
    tls:
      insecure: true

service:
  pipelines:
    traces:
      receivers: [otlp]
      processors: [memory_limiter, batch, resource]
      exporters: [otlp/tempo]
    
    metrics:
      receivers: [otlp]
      processors: [memory_limiter, batch, resource]
      exporters: [prometheus]
    
    logs:
      receivers: [otlp]
      processors: [memory_limiter, batch, resource]
      exporters: [loki]
```

Location: `observability/otel/otel-collector-config.yaml`

## Prometheus Configuration

### Scrape Configuration

```yaml
global:
  scrape_interval: 15s
  evaluation_interval: 15s

scrape_configs:
  # OTel Collector metrics endpoint
  - job_name: 'otel-collector'
    static_configs:
      - targets: ['otel-collector:8889']
  
  # Demo API metrics
  - job_name: 'demo-api'
    kubernetes_sd_configs:
      - role: pod
        namespaces:
          names: [demo]
    relabel_configs:
      - source_labels: [__meta_kubernetes_pod_label_app]
        action: keep
        regex: demo-api
      - source_labels: [__meta_kubernetes_pod_ip]
        target_label: __address__
        replacement: $1:8000
  
  # Kubernetes metrics
  - job_name: 'kubernetes-nodes'
    kubernetes_sd_configs:
      - role: node
    relabel_configs:
      - action: labelmap
        regex: __meta_kubernetes_node_label_(.+)
```

Location: `observability/prometheus/prometheus.yml`

### Recording Rules

```yaml
groups:
  - name: api_rules
    interval: 30s
    rules:
      # Availability SLI
      - record: sli:availability:ratio_rate5m
        expr: |
          sum(rate(http_requests_total{status=~"2..|3.."}[5m]))
          /
          sum(rate(http_requests_total[5m]))
      
      # Request rate by service
      - record: job:http_requests:rate5m
        expr: sum(rate(http_requests_total[5m])) by (job, method, status)
```

## Alerting

Alerts are defined in `observability/alerts/alert-rules.yml` and cover:
- High error rate
- High latency
- Pod restarts
- OOM kills
- Database saturation
- SLO burn rate

See [16-sre-slos.md](./16-sre-slos.md) for SLO alerting details.

## Dashboards

### Available Dashboards

1. **Application Overview** (`demo-api-overview.json`)
   - Request rate, error rate, latency
   - Database and Redis metrics
   - Active connections

2. **Kubernetes Health** (future)
   - Pod status
   - Resource utilization
   - Node health

3. **SRE SLOs** (future)
   - SLI current values
   - Error budget consumption
   - Burn rate alerts

4. **AI Agent Operations** (future)
   - Agent execution metrics
   - LLM cost and latency
   - Incident resolution time

### Dashboard Best Practices

- Use consistent color schemes
- Show SLI/SLO context on performance graphs
- Include alert thresholds as red lines
- Display both rate and absolute values
- Add annotations for deployments

## Querying Observability Data

### Prometheus (Metrics)

**Query examples:**
```promql
# P95 latency
histogram_quantile(0.95,
  sum(rate(http_request_duration_seconds_bucket[5m])) by (le)
)

# Error rate
sum(rate(http_requests_total{status=~"5.."}[5m]))
/
sum(rate(http_requests_total[5m]))

# Top endpoints by request count
topk(10, sum(rate(http_requests_total[5m])) by (path))
```

### Loki (Logs)

**LogQL examples:**
```logql
# Errors in last hour
{service="demo-api"} |= "ERROR"

# Requests with high latency
{service="demo-api"} | json | duration_ms > 1000

# Trace logs for specific request
{service="demo-api"} | json | correlation_id="req-abc123"
```

### Tempo (Traces)

Search by:
- Trace ID
- Service name
- Duration range
- Tag filters

## Observability in Development

### Local Setup

Use Docker Compose for local observability stack:

```yaml
# compose.yaml
services:
  otel-collector:
    image: otel/opentelemetry-collector:latest
    volumes:
      - ./observability/otel/otel-collector-config.yaml:/etc/otel-collector-config.yaml
    command: ["--config=/etc/otel-collector-config.yaml"]
    ports:
      - "4317:4317"  # OTLP gRPC
      - "4318:4318"  # OTLP HTTP
  
  prometheus:
    image: prom/prometheus:latest
    volumes:
      - ./observability/prometheus:/etc/prometheus
    ports:
      - "9090:9090"
  
  grafana:
    image: grafana/grafana:latest
    ports:
      - "3000:3000"
```

### Testing Instrumentation

1. **Verify metrics endpoint:**
   ```bash
   curl http://localhost:8000/metrics
   ```

2. **Check trace export:**
   ```bash
   # Send test request
   curl -H "traceparent: 00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01" \
        http://localhost:8000/api/health
   
   # Query Tempo for trace
   curl http://localhost:3200/api/traces/4bf92f3577b34da6a3ce929d0e0e4736
   ```

3. **Validate log structure:**
   ```bash
   docker logs demo-api 2>&1 | jq .
   ```

## Cost Optimization

Observability data can be expensive to store. Optimization strategies:

1. **Sampling:** Reduce trace volume (but always sample errors)
2. **Retention:** Shorter retention for high-volume signals
3. **Aggregation:** Use recording rules to pre-aggregate metrics
4. **Cardinality:** Limit high-cardinality labels
5. **Compression:** Enable compression in exporters

## Security Considerations

- **No secrets in logs:** Redact sensitive data
- **Access control:** Restrict Grafana/Prometheus access
- **Data retention:** Comply with data retention policies
- **PII handling:** Mask or hash personal information
- **Audit logs:** Track who accessed observability data

## Future Enhancements

1. **Real User Monitoring (RUM):** Client-side performance
2. **Synthetic monitoring:** Proactive health checks
3. **Log anomaly detection:** ML-based log analysis
4. **Continuous profiling:** CPU/memory profiling in production
5. **Cost attribution:** Per-tenant observability cost tracking

## References

- [OpenTelemetry Documentation](https://opentelemetry.io/docs/)
- [Prometheus Best Practices](https://prometheus.io/docs/practices/)
- [16-sre-slos.md](./16-sre-slos.md) - SLO implementation
- [09-incident-lifecycle.md](./09-incident-lifecycle.md) - How observability data is used
- `observability/` directory - Configuration files
