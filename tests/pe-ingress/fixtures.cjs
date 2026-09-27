"use strict";

function permitCase() {
  return {
    case_id: "permit-after-accept",
    now_ms: 1000000,
    mutate_live_loader: false,
    workload: {
      enroll_id: "wl-agent",
      workload_name: "agent",
      cgroup_id: "cg-1",
      cgroup_path: "/sys/fs/cgroup/agent",
      trace_id: "0xtrace",
      executable_path: "/opt/agent/bin",
      executable_digest: "sha256:abc",
      executable_digest_expected: "sha256:abc",
      version: "1.2.3",
      version_expected: "1.2.3",
      image_digest: null,
      image_digest_expected: null,
    },
    identity: {
      trace_id: "0xtrace",
      pid: 100,
      starttime: 50,
      comm: "agent",
      ppid: 1,
      parent_comm: "systemd",
      attested_at_ms: 995000,
      freshness_window_ms: 10000,
      credential: { presented: false },
    },
    listener: {
      proto: "tcp",
      family: "inet",
      local_addr: "0.0.0.0",
      local_port: 5000,
      iface: null,
      owner_pid: 100,
      owner_starttime: 50,
      owner_comm: "agent",
      inode_attributed: true,
    },
    envelope: {
      present: true,
      policy_id: "pol-agent",
      policy_version: "v3",
      policy_sha: "sha-applied",
      applied_sha: "sha-applied",
      candidate_sha: "sha-applied",
      last_known_sha: "sha-applied",
      fail_mode: "fail_open",
      requires_image_binding: false,
      requires_version_binding: true,
      expected_listeners: [
        { port: 5000, bind: "*", protocol: "tcp", workload: "agent", comm: "agent" },
      ],
    },
    accept: {
      proto: "tcp",
      local_addr: "0.0.0.0",
      local_port: 5000,
      remote_addr: "203.0.113.9",
      remote_port: 40000,
      accepting_pid: 100,
      accepting_starttime: 50,
      accepting_trace_id: "0xtrace",
      mechanism: "accept",
    },
    post_accept: {
      behaviors: [
        {
          kind: "open",
          path: "/opt/agent/data",
          authorized: true,
          trace_id: "0xtrace",
          cgroup_id: "cg-1",
          pid: 100,
          starttime: 50,
        },
      ],
    },
    health: {
      loader_up: true,
      evidence_writable: true,
      enroll_readable: true,
      netns_readable: true,
      trace_map_available: true,
      coverage: "seeing",
      protection_state: "observing",
    },
  };
}

function listenCase() {
  const input = structuredClone(permitCase());
  input.case_id = "expected-listener";
  input.accept = null;
  input.post_accept = { behaviors: [] };
  return input;
}

module.exports = {
  listenCase,
  permitCase,
};
