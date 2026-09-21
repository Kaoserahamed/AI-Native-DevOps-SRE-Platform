# SRE SLOs and Error Budget

This document defines Service Level Objectives, error budgets, and burn-rate alerts for the platform.

## Overview

SLOs establish reliability targets that balance innovation velocity with system stability. Error budgets quantify how much unreliability the platform can tolerate before action is required.

## Service Level Indicators (SLIs)

### Availability SLI

```
availability = successful_requests / total_requests
```

**Measurement:**
- Success: HTTP status codes 200-399
- Failure: HTTP status codes 500-599, timeouts, connection failures
- Exclusions: 400-499 client errors (not service failures)

**Source:** Prometheus `http_requests_total` metric

### Latency SLI

```
latency_sli = p99_request_duration_ms
```

**Measurement:**
- P99 latency for successful requests over rolling 5-minute windows
- Measured at ingress layer to include full request path

**Source:** Prometheus `http_request_duration_seconds` histogram

### Success Rate SLI

```
success_rate = (total_requests - error_requests) / total_requests
```

**Measurement:**
- Includes 5xx errors, timeouts, and network failures
- Measured per service

**Source:** Prometheus `http_requests_total{status="5xx"}`

## Service Level Objectives (SLOs)

### Demo API SLO

| Metric | SLO Target | Measurement Window | Error Budget |
|--------|------------|-------------------|--------------|
| Availability | 99.9% | 30 days | 43.2 minutes |
| P99 Latency | < 500ms | 5 minutes | N/A |
| Success Rate | 99.5% | 7 days | 0.5% |

### Incident Management SLO

| Metric | SLO Target | Measurement Window |
|--------|------------|-------------------|
| Detection Time | < 2 minutes | Per incident |
| Acknowledgement | < 5 minutes | Per incident |
| Incident Agent Analysis | < 3 minutes | Per incident |
| Recovery Time (P95) | < 30 minutes | 30 days |

## Error Budget Calculations

### Error Budget Formula

```
error_budget = (1 - SLO) × total_requests
```

**Example for 99.9% availability over 30 days:**
- SLO: 99.9%
- Allowed downtime: 0.1% of 30 days = 43.2 minutes
- If average RPS = 100: budget = 0.001 × 100 × 86400 × 30 = 259,200 failed requests

### Error Budget Consumption

Track budget consumption as:

```
budget_consumed = (errors_this_period / error_budget) × 100%
```

**Policy:**
- < 50%: Normal operations
- 50-80%: Elevated monitoring
- 80-100%: Freeze non-critical changes
- > 100%: Emergency - all changes blocked except incident response

## Burn Rate Alerts

Burn rate measures how quickly error budget is being consumed.

### Fast Burn (1-hour window)

```yaml
alert: SLOBurnRateHigh
expr: |
  (
    (1 - (sum(rate(http_requests_total{status=~"2..|3.."}[1h]))
          / sum(rate(http_requests_total[1h]))))
    /
    (1 - 0.999)  # SLO target
  ) > 14.4
for: 5m
```

**14.4x burn rate:** Exhausts 30-day budget in 50 hours if sustained

**Action:** Page on-call, investigate immediately

### Slow Burn (6-hour window)

```yaml
alert: SLOBurnRateWarning
expr: |
  (
    (1 - (sum(rate(http_requests_total{status=~"2..|3.."}[6h]))
          / sum(rate(http_requests_total[6h]))))
    /
    (1 - 0.999)
  ) > 1.0
for: 1h
```

**1.0x burn rate:** Exhausts budget exactly at the 30-day boundary

**Action:** Create incident ticket, schedule investigation

## Multi-Window, Multi-Burn-Rate Alerting

Following Google SRE best practices for reducing false positives:

| Alert | Short Window | Long Window | Budget Consumption | Action |
|-------|--------------|-------------|-------------------|--------|
| Critical | 1h (14.4x) | 6h (14.4x) | 2% in 1h | Page |
| High | 6h (6x) | 3d (6x) | 5% in 6h | Ticket |
| Medium | 1d (3x) | 7d (3x) | 10% in 1d | Monitor |

Both short and long windows must be in violation to fire.

## SLO Implementation

### Prometheus Recording Rules

```yaml
groups:
  - name: slo_rules
    interval: 30s
    rules:
      # Availability SLI
      - record: sli:availability:ratio_rate1h
        expr: |
          sum(rate(http_requests_total{status=~"2..|3.."}[1h]))
          /
          sum(rate(http_requests_total[1h]))

      # Latency SLI (P99)
      - record: sli:latency:p99_5m
        expr: |
          histogram_quantile(0.99,
            sum(rate(http_request_duration_seconds_bucket[5m])) by (le)
          )

      # Error budget burn rate
      - record: slo:error_budget_burn_rate:1h
        expr: |
          (1 - sli:availability:ratio_rate1h) / (1 - 0.999)
```

### Grafana Dashboard

The SLO dashboard includes:
- Current SLI values
- Error budget remaining (%)
- Error budget remaining (time)
- Burn rate trend (1h, 6h, 1d, 7d)
- Alert firing status
- Historical SLO compliance

**Location:** `observability/dashboards/sre-slo.json` (to be added)

## Incident Management SLOs

### Detection SLO

**Target:** 95% of incidents detected within 2 minutes

**Measurement:**
```
detection_time = incident.detected_at - first_alert_timestamp
```

### Acknowledgement SLO

**Target:** 95% of incidents acknowledged within 5 minutes of detection

**Measurement:**
```
ack_time = incident.acknowledged_at - incident.detected_at
```

### Mean Time to Recovery (MTTR)

**Target:** P95 MTTR < 30 minutes

**Measurement:**
```
mttr = incident.resolved_at - incident.detected_at
```

**Exclusions:** Incidents requiring human code changes (measured separately)

## Error Budget Policy

### When Budget is Healthy (< 50% consumed)

- All changes allowed
- Normal release cadence
- Experimentation encouraged

### When Budget is Elevated (50-80% consumed)

- Review deployment frequency
- Increase pre-production testing
- Defer risky changes
- Root-cause analysis required for all incidents

### When Budget is Critical (80-100% consumed)

- Freeze non-critical changes
- Focus on stability improvements
- Require SRE approval for all deployments
- Mandatory blameless postmortems

### When Budget is Exhausted (> 100% consumed)

- Change freeze except for incident response
- SLO recovery plan required
- Executive escalation
- Re-evaluate SLO targets if consistently unachievable

## SLO Review Cadence

- **Weekly:** Review error budget consumption and trend
- **Monthly:** Review SLO appropriateness and adjust if needed
- **Quarterly:** Review SLO architecture and measurement accuracy
- **Annually:** Comprehensive SLO framework review

## Reporting

### Weekly SLO Report

Generated automatically every Monday:
- SLO compliance for each service (past 7 days)
- Error budget remaining
- Top incidents by impact
- Action items

### Monthly SLO Report

- 30-day SLO compliance
- Error budget trend
- MTTR analysis
- Cost of downtime
- Recommendations

## Tools

- **Alerting:** Prometheus Alertmanager
- **Dashboards:** Grafana
- **Tracking:** PostgreSQL incident database
- **Reporting:** Python scripts in `scripts/slo_reporting/` (to be added)

## References

- Google SRE Book: https://sre.google/sre-book/service-level-objectives/
- Google SRE Workbook: https://sre.google/workbook/alerting-on-slos/
- ADR-0010: SLO Burn-Rate Alerting
- `observability/alerts/alert-rules.yml`

## Future Enhancements

1. Per-customer SLOs for multi-tenant scenarios
2. Cost-based SLO optimization
3. Synthetic monitoring integration
4. Real user monitoring (RUM) integration
5. Automated error budget enforcement in CI/CD
