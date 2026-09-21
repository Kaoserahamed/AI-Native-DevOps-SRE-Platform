# Incident Lifecycle

This document describes the complete incident lifecycle from detection through resolution and post-incident review.

## Overview

The platform implements an automated incident management workflow that integrates detection, analysis, remediation, and learning. Human oversight is maintained at critical decision points while automation handles evidence gathering, correlation, and safe action execution.

## Incident States

```
┌─────┐
│OPEN │ ← Alert triggers incident creation
└──┬──┘
   │
   ↓
┌────────────┐
│ACKNOWLEDGED│ ← SRE acknowledges awareness
└──┬─────────┘
   │
   ↓
┌──────────────┐
│INVESTIGATING │ ← Agent gathers evidence
└──┬───────────┘
   │
   ↓
┌───────────┐
│MITIGATING │ ← Remediation being applied
└──┬────────┘
   │
   ↓
┌─────────┐
│RESOLVED │ ← Service restored
└──┬──────┘
   │
   ↓
┌───────┐
│CLOSED │ ← Post-incident review complete
└───────┘
```

**State transitions:**
- OPEN → ACKNOWLEDGED (human)
- ACKNOWLEDGED → INVESTIGATING (agent/human)
- INVESTIGATING → MITIGATING (agent with approval)
- MITIGATING → RESOLVED (agent/human)
- RESOLVED → CLOSED (human)
- RESOLVED/CLOSED → OPEN (reopen if issue recurs)

## Detailed Workflow

### 1. Detection (Automated)

**Trigger Sources:**
- Prometheus alert fires
- Anomaly detection agent
- External monitoring probe
- Manual incident creation

**Actions:**
1. Alert received by incident detector
2. Incident record created with status=OPEN
3. Initial evidence attached (triggering alert)
4. Incident notification sent (Slack, PagerDuty, etc.)
5. GitHub issue created with incident summary

**SLO:** Detection within 2 minutes of actual degradation

**Data Model:**
```python
incident = Incident(
    incident_id="INC-20260921-001",
    status=IncidentStatus.OPEN,
    severity=Severity.HIGH,
    service=ServiceRef(name="demo-api", namespace="demo"),
    detected_at=datetime.now(tz=UTC),
    triggering_alerts=["HighErrorRate"],
)
```

### 2. Acknowledgement (Human)

**Purpose:** Confirm a human is aware and taking ownership

**Actions:**
1. On-call engineer receives page
2. Reviews initial incident details
3. Acknowledges via:
   - API: `POST /api/v1/incidents/{id}/acknowledge`
   - Web UI
   - Mobile app
   - ChatOps command

**SLO:** Acknowledgement within 5 minutes

**State Transition:** OPEN → ACKNOWLEDGED

### 3. Investigation (Agent-Assisted)

**Trigger:** Automatic after acknowledgement OR manual start

**Agent Actions:**
1. **Evidence Retrieval** (bounded by time window and size limits)
   - Logs from affected pods (last 15 minutes)
   - Metrics showing deviation (15-minute window)
   - Traces for failed requests
   - Recent deployment history
   - Recent configuration changes
   - Kubernetes events (pod restarts, OOM kills)

2. **Correlation Analysis**
   - Correlate deployment timing with incident start
   - Identify pod restart patterns
   - Detect database/Redis errors
   - Check resource exhaustion
   - Analyze latency/error rate changes

3. **Root Cause Hypothesis**
   - Generate suspected causes with confidence scores
   - Rank by correlation strength
   - Identify evidence gaps
   - Flag uncertainties

4. **Diagnosis Report**
   - Structured analysis with evidence citations
   - Multiple hypotheses if evidence is ambiguous
   - Explicit "insufficient evidence" outcome if applicable

**Human Role:**
- Review agent analysis
- Request additional evidence if needed
- Validate or reject hypotheses
- Provide domain knowledge the agent lacks

**SLO:** Analysis complete within 3 minutes of investigation start

**State Transition:** ACKNOWLEDGED → INVESTIGATING

**API Endpoint:** `POST /api/v1/incidents/{id}/investigate`

### 4. Mitigation (Governed Automation)

**Proposal Generation:**

The remediation agent proposes actions based on diagnosis:
- Rollback to previous version
- Restart pods
- Scale up resources
- Adjust configuration
- Traffic shifting
- Circuit breaker activation

**Each proposal includes:**
- Action type and specifics
- Risk assessment (blast radius)
- Expected impact
- Rollback plan
- Confidence level
- Required permissions

**Policy Evaluation:**

The policy engine enforces:
- No direct production mutation by agents
- Production rollback requires approval
- High-risk actions require additional approval
- Blocked namespaces/resources
- Maximum automated scope
- Rate limits
- Maintenance window restrictions

**Approval Workflow:**

1. Proposal submitted for human approval
2. Approval request includes:
   - Incident context
   - Evidence summary
   - Proposed action details
   - Risk assessment
   - Rollback plan
   - Validation results
3. Approval expires after configurable timeout (default: 60 minutes)
4. Approver makes decision:
   - **APPROVED:** Action proceeds
   - **REJECTED:** No action taken, investigation continues
   - **EXPIRED:** No action taken, requires new proposal

**Action Execution:**

Only after approval:
1. Compute action hash for audit trail
2. Execute via appropriate adapter (Kubernetes, Terraform, etc.)
3. Monitor execution progress
4. Verify expected outcome
5. Record execution result

**Rollback:**

If remediation worsens the situation:
1. Automatic detection via metrics
2. Rollback proposal generated
3. Expedited approval (or automatic if pre-authorized)
4. Execute rollback
5. Return to INVESTIGATING state

**SLO:** Mitigation execution within 5 minutes of approval

**State Transition:** INVESTIGATING → MITIGATING

**API Endpoint:** `POST /api/v1/incidents/{id}/mitigate`

### 5. Resolution (Validation)

**Validation:**
1. Monitor key metrics return to baseline
2. Error rate drops below threshold
3. Latency returns to acceptable range
4. No new alerts firing
5. Sustained stability for observation window (default: 5 minutes)

**Agent Actions:**
- Continuous monitoring during observation window
- Alert if degradation recurs
- Recommend resolution when stability confirmed

**Human Actions:**
- Review validation results
- Confirm service is actually restored (not just metrics)
- Resolve incident via API or UI

**State Transition:** MITIGATING → RESOLVED

**API Endpoint:** `POST /api/v1/incidents/{id}/resolve`

**Data:**
```json
{
  "resolution_summary": "Rolled back to v1.2.3 after deployment of v1.2.4 triggered OOM errors"
}
```

### 6. Closure (Post-Incident)

**Post-Incident Activities:**
1. Blameless postmortem (for severity >= HIGH)
2. Root cause documentation
3. Action items created
4. Monitoring/alerting improvements
5. Documentation updates
6. Knowledge base entry

**Human Actions:**
- Complete postmortem
- Add lessons learned
- Close incident via API

**State Transition:** RESOLVED → CLOSED

**API Endpoint:** `POST /api/v1/incidents/{id}/close`

**Data:**
```json
{
  "post_incident_notes": "Link to postmortem: https://..."
}
```

### 7. Reopen (If Needed)

If the same issue recurs or the incident was closed prematurely:

**State Transition:** RESOLVED/CLOSED → OPEN

**API Endpoint:** `POST /api/v1/incidents/{id}/reopen`

## Evidence Management

### Evidence Types

| Type | Source | Retention |
|------|--------|-----------|
| LOG | Application logs, platform logs | 15 days |
| METRIC | Prometheus time series | 30 days |
| TRACE | Jaeger/Tempo traces | 7 days |
| KUBERNETES | Pod events, resource states | 30 days |
| DEPLOYMENT | Git commits, deployment records | 90 days |
| CONFIGURATION | ConfigMap, Secret changes | 90 days |

### Evidence Collection Constraints

To prevent evidence collection from overwhelming the system:
- **Time window:** 15 minutes before incident, 5 minutes after
- **Log lines:** Max 1000 lines per pod
- **Metric series:** Max 100 time series
- **Traces:** Max 50 traces
- **Total size:** Max 10 MB per evidence item

### Evidence Attachment API

```http
POST /api/v1/incidents/{incident_id}/evidence
Content-Type: application/json

{
  "evidence": {
    "evidence_id": "EV-001",
    "kind": "LOG",
    "collector": "LOKI",
    "collected_at": "2026-09-21T10:30:00Z",
    "time_range_start": "2026-09-21T10:15:00Z",
    "time_range_end": "2026-09-21T10:30:00Z",
    "summary": "500 errors in demo-api",
    "data": {"log_lines": [...]}
  }
}
```

## Audit Trail

Every state transition and action is audited:

```python
audit_entry = AuditEntry(
    audit_id="AUDIT-001",
    timestamp=datetime.now(tz=UTC),
    actor_type=ActorType.HUMAN,  # or AGENT
    actor_id="user@example.com",
    action="incident.resolve",
    resource_type="incident",
    resource_id="INC-20260921-001",
    outcome="success",
    details={"resolution": "rollback completed"},
)
```

**Audit log retention:** 2 years (compliance requirement)

## Metrics and Observability

### Incident Metrics

- `incidents_total{severity, service}` - Total incidents created
- `incident_duration_seconds{severity, state}` - Time in each state
- `incident_mttr_seconds{severity}` - Mean time to resolution
- `incident_state_transitions_total{from, to}` - State transition counts

### Agent Performance Metrics

- `agent_execution_duration_seconds{agent_type}` - Agent execution time
- `agent_execution_total{agent_type, outcome}` - Agent execution outcomes
- `agent_confidence{agent_type}` - Confidence scores
- `evidence_retrieval_duration_seconds{collector}` - Evidence collection time

## Configuration

Incident lifecycle behavior is configured via environment variables and database settings:

| Parameter | Default | Description |
|-----------|---------|-------------|
| `INCIDENT_DETECTION_SLO_SECONDS` | 120 | Target detection time |
| `INCIDENT_ACK_SLO_SECONDS` | 300 | Target acknowledgement time |
| `INCIDENT_ANALYSIS_TIMEOUT_SECONDS` | 180 | Agent analysis timeout |
| `APPROVAL_EXPIRATION_MINUTES` | 60 | Approval request TTL |
| `RESOLUTION_OBSERVATION_MINUTES` | 5 | Stability window before resolution |
| `EVIDENCE_TIME_WINDOW_MINUTES` | 15 | Evidence lookback window |
| `EVIDENCE_MAX_SIZE_MB` | 10 | Max evidence payload size |

## GitHub Integration

### Incident Issue Creation

Automatically creates a GitHub issue for each incident:
- Title: `[SEVERITY] Service: Summary`
- Labels: `incident`, `severity:high`, `automated`
- Body: Full incident context, timeline, evidence, analysis

### Remediation PR Creation

When a remediation is approved:
- Branch: `remediation/{incident-id}/{proposal-id}`
- Title: `fix: remediation for incident {incident-id}`
- Body: Proposal details, risk assessment, validation
- Labels: `remediation`, `automated`
- **Note:** Never auto-merged; requires human review

## Example: End-to-End Incident

```
10:25:00 - Deployment v1.2.4 completes
10:27:30 - Error rate spikes (0.1% → 15%)
10:28:00 - HighErrorRate alert fires
10:28:05 - Incident INC-20260921-001 created (OPEN)
10:28:10 - GitHub issue created
10:28:15 - On-call engineer paged
10:29:00 - Engineer acknowledges (ACKNOWLEDGED)
10:29:05 - Investigation agent starts
10:29:30 - Evidence collected: logs, metrics, deployment history
10:30:00 - Analysis complete: "Deployment v1.2.4 caused OOM errors"
10:30:05 - Remediation proposed: "Rollback to v1.2.3"
10:30:10 - Approval requested
10:31:00 - Engineer approves rollback
10:31:05 - Rollback initiated (MITIGATING)
10:33:00 - Rollback complete, v1.2.3 deployed
10:35:00 - Metrics return to normal
10:38:00 - Stability confirmed (5-minute window)
10:38:10 - Incident resolved (RESOLVED)
10:45:00 - Remediation PR created for long-term fix
[Next day]
- Post-mortem completed
- Incident closed (CLOSED)
```

**Total MTTR:** 10 minutes (detection to resolution)

## See Also

- [08-ai-agents.md](./08-ai-agents.md) - Agent architecture
- [16-sre-slos.md](./16-sre-slos.md) - SLO definitions
- [18-governance.md](./18-governance.md) - Approval policies
- `services/incident_api/` - Incident lifecycle API implementation
- `services/incident_agent/` - Analysis agent implementation
- `services/remediation_agent/` - Remediation proposal engine
