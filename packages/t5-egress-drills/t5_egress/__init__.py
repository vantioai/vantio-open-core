"""T5 egress and side-channel decisions. Lab-only. No eBPF load."""

from t5_egress.decide import Decision, decide_dns_query, decide_dns_response
from t5_egress.decide import decide_get, decide_icmp, decide_loopback
from t5_egress.evidence import evidence_record, sha256_hex
from t5_egress.policy import Policy, load_policy, load_policy_file
from t5_egress.skb_signal import skb_label_signal
from t5_egress.symlink import open_workload_root, read_beneath
from t5_egress.volume import VolumeGate

POSTURE = (
    "PRIVATE",
    "NOT_SHIPPED",
    "INTERNAL_PROOF",
    "NO_LIVE_ATTACH",
    "NO_EBPF_LOAD",
    "NO_CLOUD_LAB",
    "LAB_ONLY",
)

__all__ = [
    "Decision",
    "POSTURE",
    "Policy",
    "VolumeGate",
    "decide_dns_query",
    "decide_dns_response",
    "decide_get",
    "decide_icmp",
    "decide_loopback",
    "evidence_record",
    "load_policy",
    "load_policy_file",
    "open_workload_root",
    "read_beneath",
    "sha256_hex",
    "skb_label_signal",
]
