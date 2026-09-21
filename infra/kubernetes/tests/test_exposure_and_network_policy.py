"""Exposure and network-segmentation expectations.

Two properties matter for a workload that an AI agent is allowed to remediate: there is exactly one public
entry point, and every network path that exists was written down on purpose. The tests below also pin the
one deliberate looseness in the base — an egress rule bounded by database *ports* because the data stores are
managed services — so it cannot quietly grow into "any port, any host".
"""

from __future__ import annotations

from infra.kubernetes.tests.conftest import DATA_STORE_PORTS, Manifest, by_kind
import pytest

pytestmark = pytest.mark.unit


def test_services_are_cluster_internal(base_manifests: list[Manifest]) -> None:
    """A NodePort or LoadBalancer service would publish the workload without any review."""
    services = by_kind(base_manifests, "Service")

    assert services, "the base defines no Service"
    for service in services:
        # ClusterIP is the default; stating it explicitly keeps the intent readable.
        assert service.document["spec"].get("type", "ClusterIP") == "ClusterIP", (
            f"{service.identifier} is exposed beyond the cluster"
        )


def test_the_ingress_publishes_only_the_frontend(base_manifests: list[Manifest]) -> None:
    """One entry point: the browser reaches the API through the frontend's `/api` proxy, never directly."""
    ingress = by_kind(base_manifests, "Ingress")

    assert len(ingress) == 1, "expected exactly one Ingress"
    spec = ingress[0].document["spec"]
    assert spec.get("ingressClassName"), (
        "no ingress class is selected, so any controller may serve it"
    )
    backends = [
        path["backend"]["service"]["name"]
        for rule in spec["rules"]
        for path in rule["http"]["paths"]
    ]

    assert backends == ["demo-web"], f"the Ingress also publishes {set(backends) - {'demo-web'}}"


def test_the_namespace_denies_all_traffic_by_default(base_manifests: list[Manifest]) -> None:
    """Every allowed path must be an explicit exception, not an oversight."""
    policies = by_kind(base_manifests, "NetworkPolicy")
    default_deny = [policy for policy in policies if policy.name == "default-deny-all"]

    assert len(default_deny) == 1, "the namespace has no default-deny NetworkPolicy"
    spec = default_deny[0].document["spec"]
    assert spec["podSelector"] == {}, "the default-deny policy does not select every pod"
    assert set(spec["policyTypes"]) == {"Ingress", "Egress"}


def test_ingress_to_the_api_comes_only_from_the_frontend(base_manifests: list[Manifest]) -> None:
    """The API's ingress rule must name the frontend pods rather than allow the namespace."""
    policy = next(
        policy
        for policy in by_kind(base_manifests, "NetworkPolicy")
        if policy.name == "allow-web-to-api"
    )
    selector = policy.document["spec"]["podSelector"]["matchLabels"]

    assert selector == {"app.kubernetes.io/name": "demo-api"}
    sources = policy.document["spec"]["ingress"][0]["from"]
    assert sources == [{"podSelector": {"matchLabels": {"app.kubernetes.io/name": "demo-web"}}}]


def test_egress_is_bounded(base_manifests: list[Manifest]) -> None:
    """An egress rule without an address must be limited to the data-store ports."""
    for policy in by_kind(base_manifests, "NetworkPolicy"):
        egress = policy.document["spec"].get("egress", [])
        for index, rule in enumerate(egress):
            if "to" in rule:
                continue
            ports = {port["port"] for port in rule.get("ports", [])}
            assert ports <= DATA_STORE_PORTS, (
                f"{policy.identifier} egress rule {index} reaches any address on ports {ports}"
            )


def test_every_pod_gets_dns_and_nothing_more_by_default(base_manifests: list[Manifest]) -> None:
    """DNS is the one egress path shared by the whole namespace."""
    policies = by_kind(base_manifests, "NetworkPolicy")
    dns = next(policy for policy in policies if policy.name == "allow-dns-egress")

    assert dns.document["spec"]["podSelector"] == {}
    ports = {
        (port["protocol"], port["port"]) for port in dns.document["spec"]["egress"][0]["ports"]
    }
    assert ports == {("UDP", 53), ("TCP", 53)}


def test_overlays_do_not_reintroduce_unbounded_egress(overlay_manifests: list[Manifest]) -> None:
    """Production replaces the port-bounded rule with explicit addresses; this guards the intent."""
    for policy in by_kind(overlay_manifests, "NetworkPolicy"):
        for index, rule in enumerate(policy.document["spec"].get("egress", [])):
            assert "to" in rule, (
                f"{policy.identifier} egress rule {index} has no address restriction"
            )
            for target in rule["to"]:
                if "ipBlock" in target:
                    assert target["ipBlock"]["cidr"] != "0.0.0.0/0", (
                        f"{policy.identifier} allows egress to every address"
                    )
