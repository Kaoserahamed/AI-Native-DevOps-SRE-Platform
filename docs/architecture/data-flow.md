# Data Flow Architecture

This document describes how data flows through the AI-Native DevOps & SRE Platform.

## Overview

The platform processes three primary data flows:
1. **Telemetry Flow**: Application → Observability Systems
2. **Incident Flow**: Detection → Analysis → Remediation → Resolution
3. **Audit Flow**: All actions → Audit Log → Compliance

## 1. Telemetry Data Flow

### Application Instrumentation

```
┌──────────────┐
│ Application  │
│   (FastAPI)  │
└──────┬───────┘
       │
       ├─→ Logs (JSON structured)
       ├─→ Metrics (Prometheus format)
       └─→ Traces (OTLP)
       │
       ↓
┌────────────────────┐
│ OpenTelemetry SDK  │
│  - Logging         │
│  - Metrics         │
│  - Tracing         │
└──────┬─────────────┘
       │ (OTLP gRPC/HTTP)
       ↓
┌──────────────────────────┐
│ OTel Collector           │
│  - Receive               │
│  - Batch & Buffer        │
│  - Enrich (resource)     │
│  - Sample (traces)       │
└──────┬───────────────────┘
       │
       ├─→ Prometheus (metrics)
       ├─→ Loki (logs)
       └─→ Tempo (traces)
```

### Data Characteristics

| Signal | Format | Volume | Retention |
|--------|--------|--------|-----------|
| Logs | JSON | ~10 MB/day | 30 days |
| Metrics | Prometheus | ~100k samples/day | 90 days |
| Traces | OTLP | ~1k spans/day (sampled) | 7 days |

### Correlation

All signals are correlated via:
- **Correlation ID**: Generated at ingress, propagated via headers
- **Trace ID**: OpenTelemetry trace identifier
- **Span ID**: Current span within trace
- **Timestamps**: ISO 8601 format with microsecond precision

Example log entry:
```json
{
  "timestamp": "2026-09-21T10:30:45.123456Z",
  "level": "INFO",
  "message": "Request processed",
  "correlation_id": "req-abc123",
  "trace_id": "4bf92f3577b34da6a3ce929d0e0e4736",
  "span_id": "00f067aa0ba902b7",
  "service": "demo-api",
  "duration_ms": 45,
  "status_code": 200
}
```

## 2. Incident Management Data Flow

### Phase 1: Detection

```
Prometheus Alert Manager
       ↓
  Alert Payload
       ↓
Incident Detector
       ↓
Create Incident Record
  (PostgreSQL)
       ↓
Emit Incident Event
```

**Alert Payload Example**:
```json
{
  "alert_name": "HighErrorRate",
  "severity": "critical",
  "service": "demo-api",
  "namespace": "demo",
  "firing_at": "2026-09-21T10:30:00Z",
  "labels": {
    "severity": "critical",
    "service": "demo-api"
  },
  "annotations": {
    "summary": "Error rate above 5%",
    "description": "Current rate: 12.3%"
  }
}
```

### Phase 2: Evidence Collection

```
Incident Created
       ↓
Evidence Collector (parallel)
       ├─→ Query Loki for logs
       ├─→ Query Prometheus for metrics
       ├─→ Query Tempo for traces
       ├─→ Query Kubernetes API for events
       └─→ Query GitHub for deployments
       ↓
Evidence Items (bounded)
  - Time window: 15 min
  - Size limit: 10 MB per item
  - Max items: 50
       ↓
Store Evidence
  (PostgreSQL)
```

**Evidence Schema**:
```python
Evidence(
    evidence_id="EV-001",
    incident_id="INC-001",
    kind="LOG",  # LOG, METRIC, TRACE, KUBERNETES, DEPLOYMENT
    collector="LOKI",
    collected_at=datetime.now(),
    time_range_start=incident_start - 15min,
    time_range_end=incident_start,
    summary="500 errors detected",
    data={"logs": [...]},
    size_bytes=2048000
)
```

### Phase 3: Analysis

```
Evidence Collection Complete
       ↓
Anomaly Detector
  - Baseline comparison
  - Threshold checks
  - Rate-of-change analysis
       ↓
Root Cause Correlator
  - Deployment correlation
  - Pod restart patterns
  - Database errors
  - Redis errors
  - Application errors
       ↓
Suspected Causes (ranked by confidence)
       ↓
Incident Agent (LLM)
  Input:
    - Alert details
    - Evidence items
    - Suspected causes
    - Recent deployments
  Output:
    - Diagnosis text
    - Confidence score
    - Evidence citations
    - Uncertainties
       ↓
Update Incident with Analysis
  (PostgreSQL)
```

**Analysis Output Schema**:
```python
AnalysisResult(
    incident_id="INC-001",
    diagnosis="Recent deployment v1.2.4 introduced OOM errors",
    confidence=0.85,
    suspected_causes=[
        SuspectedCause(
            category="DEPLOYMENT",
            description="v1.2.4 deployed 2min before incident",
            confidence=0.9,
            evidence_ids=["EV-001", "EV-003"],
        )
    ],
    evidence_citations=["EV-001", "EV-002", "EV-003"],
    uncertainties=["Memory limits not visible in logs"],
    analyzed_at=datetime.now(),
)
```

### Phase 4: Remediation Proposal

```
Analysis Complete
       ↓
Remediation Agent
  Input:
    - Diagnosis
    - Suspected causes
    - Service configuration
  Output:
    - Action type (rollback, restart, scale, config)
    - Specific parameters
    - Risk assessment
    - Blast radius
    - Rollback plan
       ↓
Policy Engine Evaluation
  Checks:
    - Not direct production mutation
    - Within allowed scope
    - No blocked resources
    - Respects rate limits
  Result:
    - ALLOW
    - BLOCK
    - REQUIRE_APPROVAL
       ↓
Store Proposal
  (PostgreSQL)
```

**Proposal Schema**:
```python
RemediationProposal(
    proposal_id="PROP-001",
    incident_id="INC-001",
    action_type="ROLLBACK",
    action_details={
        "from_version": "v1.2.4",
        "to_version": "v1.2.3",
        "service": "demo-api",
        "namespace": "demo",
    },
    risk_level="HIGH",
    blast_radius="SERVICE",  # POD, SERVICE, NAMESPACE, CLUSTER
    expected_impact="Service downtime: 30-60 seconds",
    rollback_plan="Rollback to v1.2.4 if errors persist",
    confidence=0.85,
    requires_approval=True,
    policy_result="REQUIRE_APPROVAL",
)
```

### Phase 5: Approval Workflow

```
Proposal Created
       ↓
Create Approval Request
  - Proposal ID
  - Action hash (for idempotency)
  - Approver(s)
  - Expiration (60 minutes default)
       ↓
Notify Approver
  (Slack, email, etc.)
       ↓
Human Decision
  - APPROVED
  - REJECTED
  - EXPIRED (timeout)
       ↓
Store Approval Decision
  (PostgreSQL)
       ↓
If APPROVED:
    Execute Remediation
```

**Approval Schema**:
```python
Approval(
    approval_id="APPR-001",
    proposal_id="PROP-001",
    incident_id="INC-001",
    action_hash="sha256:abc123...",
    approver_id="user@example.com",
    decision="APPROVED",
    comment="Rollback approved, matches diagnosis",
    decided_at=datetime.now(),
    expires_at=datetime.now() + timedelta(minutes=60),
)
```

### Phase 6: Execution & Audit

```
Approval Granted
       ↓
GitHub Adapter
  1. Create branch
  2. Commit changes
  3. Open PR
       ↓
CI Runs on PR
  - Lint
  - Test
  - Security scan
  - Manifest validation
       ↓
Manual Review & Merge
       ↓
CD Pipeline
  - Build images
  - Deploy to environment
  - Verify deployment
       ↓
Update Incident Status
  - MITIGATING → RESOLVED
       ↓
Create Audit Trail
```

**Audit Entry Schema**:
```python
AuditEntry(
    audit_id="AUDIT-001",
    timestamp=datetime.now(),
    actor_type="AGENT",  # or HUMAN
    actor_id="remediation-agent",
    action="remediation.execute",
    resource_type="incident",
    resource_id="INC-001",
    outcome="success",
    details={
        "proposal_id": "PROP-001",
        "approval_id": "APPR-001",
        "pr_url": "https://github.com/org/repo/pull/123",
        "action_hash": "sha256:abc123...",
    },
)
```

## 3. Query Patterns

### Real-time Queries

**By Correlation ID** (across all signals):
```
Logs:   {correlation_id="req-abc123"}
Metrics: http_requests_total{correlation_id="req-abc123"}
Traces: trace_id=4bf92f3577b34da6a3ce929d0e0e4736
```

**By Incident ID**:
```sql
-- Get all evidence for incident
SELECT * FROM evidence WHERE incident_id = 'INC-001';

-- Get incident timeline
SELECT event_type, timestamp, details
FROM audit_log
WHERE resource_id = 'INC-001'
ORDER BY timestamp;
```

### Analytical Queries

**SLO Calculation**:
```promql
# Availability SLI
sum(rate(http_requests_total{status=~"2..|3.."}[1h]))
/
sum(rate(http_requests_total[1h]))
```

**Incident MTTR**:
```sql
SELECT
    AVG(EXTRACT(EPOCH FROM (resolved_at - detected_at))/60) as mttr_minutes
FROM incidents
WHERE resolved_at IS NOT NULL
AND detected_at > NOW() - INTERVAL '30 days';
```

## 4. Data Retention Policies

| Data Type | Retention | Rationale |
|-----------|-----------|-----------|
| Logs | 30 days | Debugging, compliance |
| Metrics | 90 days | Trend analysis, capacity planning |
| Traces | 7 days | Recent incident investigation |
| Incidents | 2 years | Historical analysis, compliance |
| Evidence | 90 days | Incident replay, training |
| Audit logs | 2 years | Compliance, security |
| Approvals | 2 years | Governance audit |

## 5. Data Privacy & Security

### PII Handling
- **Redaction**: User IDs, emails masked in logs
- **Hashing**: Sensitive identifiers hashed before storage
- **Access Control**: RBAC for observability data

### Secrets
- **Never logged**: Credentials, tokens, keys
- **Encrypted**: At rest in PostgreSQL, in transit via TLS
- **Scoped access**: Secrets accessible only to authorized services

### Compliance
- **GDPR**: Right to deletion, data minimization
- **SOC 2**: Audit logs, access controls
- **HIPAA** (if applicable): Encryption, access logs

## 6. Performance Characteristics

### Latency Targets

| Operation | Target | p99 |
|-----------|--------|-----|
| Log ingestion | < 100ms | 200ms |
| Metric scrape | < 1s | 2s |
| Trace export | < 500ms | 1s |
| Evidence query | < 5s | 10s |
| LLM analysis | < 30s | 60s |
| Approval decision | Human-driven | N/A |

### Throughput

| Signal | Rate | Peak |
|--------|------|------|
| Logs | 1000/sec | 5000/sec |
| Metrics | 10k samples/sec | 50k/sec |
| Traces | 100/sec | 500/sec |
| Incidents | 10/hour | 100/hour |

## 7. Data Flow Monitoring

### Observability of Observability

**Metrics**:
```
otel_collector_received_spans
otel_collector_exported_spans
prometheus_rule_evaluations_total
loki_ingester_chunks_flushed_total
```

**Alerts**:
- OTel Collector down
- Prometheus scrape failures
- Loki ingestion lag
- High evidence collection latency

### Data Quality

**Validation**:
- Schema validation at ingestion
- Timestamp ordering checks
- Size limit enforcement
- Correlation ID presence

**Monitoring**:
```
evidence_collection_errors_total
llm_invalid_response_total
approval_expiration_total
```

## References

- [System Architecture](system-architecture.md)
- [Observability](../07-observability.md)
- [Incident Lifecycle](../09-incident-lifecycle.md)
- [Database Schema](../adr/0004-postgresql-storage.md)
