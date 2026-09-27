"use strict";

function parseV4(ip) {
  const parts = String(ip).split(".");
  if (parts.length !== 4) return null;
  const nums = [];
  for (const part of parts) {
    if (!/^\d{1,3}$/.test(part)) return null;
    const n = Number(part);
    if (n > 255) return null;
    nums.push(n);
  }
  return (((nums[0] << 24) | (nums[1] << 16) | (nums[2] << 8) | nums[3]) >>> 0);
}

function isPrivateV4(hostOrder) {
  const word = hostOrder >>> 0;
  if ((word & 0xff000000) >>> 0 === 0x7f000000) return true;
  if ((word & 0xff000000) >>> 0 === 0x0a000000) return true;
  if ((word & 0xfff00000) >>> 0 === 0xac100000) return true;
  if ((word & 0xffff0000) >>> 0 === 0xc0a80000) return true;
  if ((word & 0xffff0000) >>> 0 === 0xa9fe0000) return true;
  return false;
}

function cidrMask(width) {
  if (width === 0) return 0;
  return (0xffffffff << (32 - width)) >>> 0;
}

function cidrMatchV4(ip, cidr) {
  const [net, widthText] = String(cidr).split("/");
  const width = Number(widthText);
  if (!Number.isInteger(width) || width < 0 || width > 32) return false;
  const ipn = parseV4(ip);
  const netn = parseV4(net);
  if (ipn === null || netn === null) return false;
  const mask = cidrMask(width);
  return (ipn & mask) === (netn & mask);
}

function enrolled(host, cgroupId) {
  if (typeof cgroupId !== "number" || cgroupId === 0) return false;
  return host.enrolled_cgroups.includes(cgroupId);
}

function planeGate(host, attempt) {
  const plane = attempt.plane || "tc";
  if (plane === "cgroup_skb" && host.cgroup_skb_attached !== true) {
    return {
      disposition: "NOT_COVERED",
      mechanism_id: "cgroup_skb_opt_in",
      reason: "cgroup_skb_not_attached",
      kernel_executed: false,
    };
  }
  const mechanism_id = plane === "cgroup_skb" ? "cgroup_skb_opt_in" : "tc_scoped_egress";
  const mode = host.mode;
  if (mode !== "scoped" && mode !== "node_wide") {
    return {
      disposition: "CITED_ALLOW",
      mechanism_id,
      reason: mode === "audit" ? "audit_mode" : "unknown_mode_does_not_drop",
      protection_state_claimed: null,
      kernel_executed: false,
    };
  }
  // TC scoped mode consults the enrolled map. cgroup_skb does not: the loader's
  // attach is the scope, and a detached program is already returned above.
  if (plane === "tc" && mode === "scoped" && !enrolled(host, attempt.cgroup_id)) {
    return {
      disposition: "CITED_ALLOW",
      mechanism_id,
      reason: attempt.cgroup_id === 0 ? "cgroup_id_0" : "cgroup_not_enrolled",
      kernel_executed: false,
    };
  }
  const severed = host.severed_pids || [];
  if (typeof attempt.pid === "number" && severed.includes(attempt.pid)) {
    return {
      disposition: "CITED_DROP",
      mechanism_id: "tls_content_sever",
      reason: "tls_content_sever_pid",
      kernel_executed: false,
    };
  }
  return { continue: true, mechanism_id };
}

function decideV4(host, attempt) {
  const gate = planeGate(host, attempt);
  if (!gate.continue) return gate;
  const { mechanism_id } = gate;
  const ip = parseV4(attempt.dest);
  if (ip === null) {
    return {
      disposition: "CITED_ALLOW",
      mechanism_id,
      reason: "unparsed_destination_does_not_drop",
      kernel_executed: false,
    };
  }
  if (isPrivateV4(ip)) {
    return { disposition: "CITED_ALLOW", mechanism_id, reason: "private_or_link_local", kernel_executed: false };
  }
  if (host.sever_cidr_v4.some((cidr) => cidrMatchV4(attempt.dest, cidr))) {
    return { disposition: "CITED_DROP", mechanism_id, reason: "sever_cidr", kernel_executed: false };
  }
  const protocol = attempt.protocol || "tcp";
  if (protocol === "tcp" && host.blocked_tcp_ports.includes(attempt.port)) {
    return { disposition: "CITED_DROP", mechanism_id, reason: "blocked_tcp_port", kernel_executed: false };
  }
  if (host.allow_exact_v4.includes(attempt.dest)) {
    return { disposition: "CITED_ALLOW", mechanism_id, reason: "exact_allow", kernel_executed: false };
  }
  if (host.allow_cidr_v4.some((cidr) => cidrMatchV4(attempt.dest, cidr))) {
    return { disposition: "CITED_ALLOW", mechanism_id, reason: "cidr_allow", kernel_executed: false };
  }
  return { disposition: "CITED_DROP", mechanism_id, reason: "not_allowlisted", kernel_executed: false };
}

function parseV6Prefix(addr) {
  const text = String(addr).toLowerCase();
  if (text.includes(".")) return null;
  const halves = text.split("::");
  if (halves.length > 2) return null;
  const left = halves[0] ? halves[0].split(":") : [];
  const right = halves.length === 2 && halves[1] ? halves[1].split(":") : [];
  if (halves.length === 1 && left.length !== 8) return null;
  const missing = 8 - (left.length + right.length);
  if (halves.length === 2 && missing < 1) return null;
  const groups = halves.length === 2 ? left.concat(Array(missing).fill("0"), right) : left;
  if (groups.length !== 8) return null;
  const nums = [];
  for (const group of groups) {
    if (!/^[0-9a-f]{1,4}$/.test(group)) return null;
    nums.push(parseInt(group, 16));
  }
  return nums;
}

function decideV6(host, attempt) {
  const gate = planeGate(host, attempt);
  if (!gate.continue) return gate;
  const { mechanism_id } = gate;
  if (host.allow_cidr_v6.length > 0 || (attempt.sever_cidr_v6 && attempt.sever_cidr_v6.length > 0)) {
    return {
      disposition: "NOT_REIMPLEMENTED",
      mechanism_id,
      reason: "ipv6_lpm",
      kernel_executed: false,
    };
  }
  const groups = parseV6Prefix(attempt.dest);
  if (!groups) {
    return {
      disposition: "CITED_ALLOW",
      mechanism_id,
      reason: "unparsed_destination_does_not_drop",
      kernel_executed: false,
    };
  }
  const prefix = groups[0];
  if ((prefix & 0xfe00) === 0xfc00) {
    return { disposition: "CITED_ALLOW", mechanism_id, reason: "ula", kernel_executed: false };
  }
  if ((prefix & 0xffc0) === 0xfe80) {
    return { disposition: "CITED_ALLOW", mechanism_id, reason: "link_local", kernel_executed: false };
  }
  const canonical = groups.map((n) => n.toString(16)).join(":");
  const allowed = host.allow_exact_v6.map((item) => {
    const parsed = parseV6Prefix(item);
    return parsed ? parsed.map((n) => n.toString(16)).join(":") : item;
  });
  if (allowed.includes(canonical)) {
    return { disposition: "CITED_ALLOW", mechanism_id, reason: "exact_allow", kernel_executed: false };
  }
  return { disposition: "CITED_DROP", mechanism_id, reason: "not_allowlisted", kernel_executed: false };
}

module.exports = {
  parseV4,
  isPrivateV4,
  cidrMatchV4,
  enrolled,
  decideV4,
  decideV6,
};
