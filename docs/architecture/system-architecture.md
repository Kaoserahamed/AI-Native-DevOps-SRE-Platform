# System Architecture

This document describes the high-level architecture of the AI-Native DevOps & SRE Platform.

## Overview

The platform implements a closed-loop incident management system that detects degradations, diagnoses root causes using AI, proposes remediation actions, enforces policy and approval gates, and applies fixes through auditable pull requests.

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                        Control Plane                             │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌──────────┐  ┌──────────────┐  ┌────────────┐  ┌──────────┐ │
│  │ Incident │  │  Anomaly     │  │Remediation │  │ Approval │ │
│  │  Agent   │→ │  Detection   │→ │   Agent    │→ │   API    │ │
│  └──────────┘  └──────────────┘  └────────────┘  └──────────┘ │
│       ↑                                                 ↓        │
│       │                                                 ↓        │
│       │                                          ┌──────────┐   │
│       │                                          │  GitHub  │   │
│       │                                          │ Adapter  │   │
│       │                                          └──────────┘   │
│       │                                                 ↓        │
└───────┼─────────────────────────────────────────────────────────┘
        │                                                 ↓
┌───────┼─────────────────────────────────────────────────────────┐
│       │                  Data Plane                     ↓        │
├───────┼─────────────────────────────────────────────────────────┤
│       │                                                 ↓        │
│  ┌────┴────┐  ┌──────────────┐  ┌────────────┐  ┌────▼────┐  │
│  │  Alert  │  │  Evidence    │  │ Observ-    │  │   PR    │  │
│  │ Manager │  │  Collector   │  │ ability    │  │Creation │  │
│  └─────────┘  └──────────────┘  └────────────┘  └─────────┘  │
│       ↑              ↑                 ↑                        │
└───────┼──────────────┼─────────────────┼────────────────────────┘
        │              │                 │
┌───────┼──────────────┼─────────────────┼────────────────────────┐
│       │     Infrastructure Layer       │                        │
├───────┼──────────────┼─────────────────┼────────────────────────┤
│       │              │                 │                        │
│  ┌────┴────┐  ┌──────▼──────┐  ┌──────▼──────┐               │
│  │Prometheus│  │ OpenTelem-  │  │ Demo        │               │
│  │         │  │   etry      │  │Application  │               │
│  └─────────┘  │ Collector   │  └─────────────┘               │
│               └─────────────┘                                  │
│                                                                 │
│  ┌────────┐  ┌────────┐  ┌────────┐  ┌────────────┐         │
│  │Postgres│  │ Redis  │  │  Loki  │  │   Tempo    │         │
│  └────────┘  └────────┘  └────────┘  └────────────┘         │
│                                                                 │
│                    Kubernetes Cluster                          │
└─────────────────────────────────────────────────────────────────┘
```

## Core Components

### Control Plane Services

#### 1. Incident Agent
**Purpose**: Analyzes incidents using LLM-powered reasoning

**Responsibilities**:
- Normalize incoming alerts
- Orchestrate evidence collection
- Correlate signals across logs, metrics, traces
- Generate diagnosis with confidence scores
- Identify uncertainties and evidence gaps

**Technology**: Python/FastAPI, OpenAI/Anthropic LLM
**Location**: `services/incident_agent/`

#### 2. Anomaly Detection
**Purpose**: Detect statistical anomalies in telemetry data

**Responsibilities**:
- Maintain rolling baselines
- Detect threshold breaches
- Calculate z-score outliers
- Identify rate-of-change anomalies
- Deduplicate alerts
- Correlate related anomalies

**Technology**: Python, statistical methods
**Location**: `services/anomaly_agent/`

#### 3. Remediation Agent
**Purpose**: Propose safe remediation actions

**Responsibilities**:
- Generate remediation proposals (rollback, restart, scale, configure)
- Calculate blast radius and risk level
- Provide rollback plans
- Ensure evidence-based recommendations

**Technology**: Python
**Location**: `services/remediation_agent/`

#### 4. Policy Engine
**Purpose**: Enforce governance rules

**Responsibilities**:
- No direct production mutation
- Require approval for high-risk actions
- Blocked namespace enforcement
- Rate limiting
- Maintenance window restrictions

**Technology**: Python
**Location**: `services/remediation_agent/policy.py`

#### 5. Approval API
**Purpose**: Human-in-the-loop approval workflow

**Responsibilities**:
- Create approval requests with expiration
- Track approver identity
- Bind approvals to action hashes
- Audit all decisions

**Technology**: Python/FastAPI
**Location**: `services/approval_api/`

#### 6. GitHub Adapter
**Purpose**: Automate issue and PR creation

**Responsibilities**:
- Create incident issues with evidence
- Generate remediation PRs
- Manage branches and commits
- Track deployment history

**Technology**: Python, GitHub API
**Location**: `packages/github_client/`

### Data Plane Services

#### 7. Demo Application
**Purpose**: Generate realistic production telemetry

**Components**:
- **Backend**: FastAPI service with PostgreSQL/Redis
- **Frontend**: Next.js application

**Features**:
- Health/readiness endpoints
- Structured logging
- Metrics export
- Distributed tracing
- Controllable failure modes

**Location**: `apps/demo-app/`

#### 8. OpenTelemetry Collector
**Purpose**: Centralized telemetry collection and routing

**Responsibilities**:
- Receive OTLP traces, metrics, logs
- Batch and enrich data
- Export to backend systems
- Resource attribute injection

**Configuration**: `observability/otel/otel-collector-config.yaml`

#### 9. Prometheus
**Purpose**: Metrics storage and alerting

**Responsibilities**:
- Scrape metrics endpoints
- Execute recording rules
- Evaluate alert rules
- Store time series data

**Configuration**: `observability/prometheus/prometheus.yml`

#### 10. Incident API
**Purpose**: Incident lifecycle management

**Responsibilities**:
- CRUD operations for incidents
- State machine transitions
- Evidence attachment
- Status tracking

**Location**: `services/incident_api/`

### Infrastructure Layer

#### 11. PostgreSQL
**Purpose**: Primary data store

**Stores**:
- Incidents and evidence
- Audit logs
- Approval records
- Agent execution history

**Schema**: `migrations/`

#### 12. Redis
**Purpose**: Cache and job queue

**Uses**:
- Session storage
- Rate limiting
- Background job queue
- Temporary data cache

#### 13. Grafana
**Purpose**: Visualization and dashboards

**Dashboards**:
- Application overview
- Kubernetes health
- SRE SLOs
- AI agent operations

**Configuration**: `observability/dashboards/`

#### 14. Loki
**Purpose**: Log aggregation

**Responsibilities**:
- Collect structured logs
- Support LogQL queries
- Retain logs per policy

#### 15. Tempo
**Purpose**: Distributed tracing backend

**Responsibilities**:
- Store trace spans
- Support trace queries
- Correlate with logs/metrics

## Data Flow

### 1. Detection Flow

```
Application → OTel Collector → Prometheus → Alert Rules → Incident Created
                             ↓
                          Loki (logs)
                             ↓
                          Tempo (traces)
```

### 2. Analysis Flow

```
Incident → Evidence Collector → [Logs, Metrics, Traces, K8s Events, Deployments]
                              ↓
                         Correlation Engine
                              ↓
                         Incident Agent (LLM)
                              ↓
                         Diagnosis + Confidence
```

### 3. Remediation Flow

```
Diagnosis → Remediation Agent → Proposal
                              ↓
                         Policy Engine → [Allow/Block/Require Approval]
                              ↓
                         Approval API → Human Decision
                              ↓
                         GitHub Adapter → PR Creation
                              ↓
                         CI/CD → Deployment
```

## Trust Boundaries

### Boundary 1: External Input
**Between**: Internet/Users → Application
**Controls**: Input validation, rate limiting, authentication

### Boundary 2: Observability Data
**Between**: Application → Telemetry Systems
**Controls**: Treat as untrusted, sanitize before LLM, size limits

### Boundary 3: AI Agent
**Between**: Agent → Production Actions
**Controls**: Policy engine, approval requirement, audit trail

### Boundary 4: GitHub Integration
**Between**: Platform → GitHub
**Controls**: Least-privilege tokens, PR-only changes, no auto-merge

## Communication Patterns

### Synchronous (HTTP/gRPC)
- User → Demo Application
- Services → PostgreSQL/Redis
- Application → OTel Collector
- Agent → LLM Provider
- Adapter → GitHub API

### Asynchronous (Queue)
- Alert → Incident Creation
- Incident → Agent Analysis
- Proposal → Approval Request

### Event-Driven
- Alert fires → Incident created
- Approval granted → Remediation triggered
- Deployment complete → Notification sent

## Failure Domains

### Domain 1: Application
**Failures**: Pod crash, OOM, application bugs
**Impact**: User-facing degradation
**Detection**: Health checks, error rates, latency

### Domain 2: Infrastructure
**Failures**: Node failure, network partition, storage issues
**Impact**: Multi-service degradation
**Detection**: Kubernetes events, node metrics

### Domain 3: Data Layer
**Failures**: Database unavailable, Redis failure
**Impact**: Data operations fail
**Detection**: Connection errors, query timeouts

### Domain 4: Observability
**Failures**: Collector crash, Prometheus down
**Impact**: Blind to incidents
**Detection**: Self-monitoring, heartbeats

### Domain 5: Control Plane
**Failures**: Agent timeout, LLM provider outage
**Impact**: No automated diagnosis
**Detection**: Agent execution metrics, timeouts

## Scalability Considerations

### Horizontal Scaling
- Demo application (stateless)
- Incident API (stateless)
- Approval API (stateless)
- OTel Collector (stateless)

### Vertical Scaling
- PostgreSQL (primary)
- Prometheus (metrics storage)
- Agent inference (LLM calls)

### Bottlenecks
1. **LLM API rate limits**: Implement queueing and retries
2. **Database connections**: Connection pooling
3. **Evidence collection**: Size limits and timeouts
4. **Prometheus cardinality**: Metric aggregation

## Security Architecture

### Authentication
- Service-to-service: mTLS or service mesh
- User-to-service: JWT tokens
- GitHub: Personal access tokens (PAT) or GitHub App

### Authorization
- RBAC for Kubernetes resources
- Policy engine for agent actions
- Approval workflow for production changes

### Secrets Management
- Kubernetes Secrets for credentials
- External secrets operator (future)
- No secrets in code or containers

### Network Security
- NetworkPolicies (default-deny)
- Pod Security Standards (restricted)
- TLS for all external communication

## Observability Architecture

### Logs
**Format**: JSON structured
**Correlation**: Request ID, trace ID, span ID
**Retention**: 30 days

### Metrics
**Format**: Prometheus/OpenMetrics
**Cardinality**: Controlled via recording rules
**Retention**: 90 days

### Traces
**Format**: OpenTelemetry
**Sampling**: 10% (100% for errors)
**Retention**: 7 days

## Deployment Architecture

### Environments
1. **Development**: Local Docker Compose
2. **Staging**: Kubernetes cluster, reduced scale
3. **Production**: Kubernetes cluster, full scale

### Deployment Strategy
- **Application**: Rolling updates
- **Infrastructure**: Blue/green or canary
- **Rollback**: Automated via GitOps

### CI/CD Pipeline
```
Code Push → CI Checks → Build Images → Scan → Deploy Staging → E2E Tests → Production Approval → Deploy Production
```

## Future Enhancements

1. **Multi-tenancy**: Isolate incidents per customer
2. **Advanced ML**: Replace statistical anomaly detection with ML models
3. **Cost optimization**: Track and optimize cloud costs
4. **Chaos engineering**: Automated fault injection
5. **Self-healing**: Automatic remediation for known issues

## References

- [Data Flow Diagram](data-flow.md)
- [Decision Records](../adr/)
- [API Documentation](../01-architecture.md)
- [Security Model](../18-governance.md)
