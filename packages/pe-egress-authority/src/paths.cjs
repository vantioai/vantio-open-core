"use strict";

// Path catalog grounded in open-core at 89f95099 and in the wave-1 coverage
// matrix. Host rows are declarations. This package does not load eBPF.

function app(id, support, caps, source) {
  return {
    id,
    plane: "application",
    support,
    source,
    seesHttp: !!caps.seesHttp,
    seesResolvedIp: !!caps.seesResolvedIp,
    redirectReeval: false,
    dnsRecheck: false,
    redactMaterialized: !!caps.redactMaterialized,
    sizeGate: !!caps.sizeGate,
    spendSubsequent: !!caps.spendSubsequent,
    directSocket: !!caps.directSocket,
    childTool: !!caps.childTool,
    tlsPeerVerified: false,
    hostDrop: false,
  };
}

function host(id, support, source) {
  return {
    id,
    plane: "host",
    support,
    source,
    seesHttp: false,
    seesResolvedIp: true,
    redirectReeval: false,
    dnsRecheck: false,
    redactMaterialized: false,
    sizeGate: false,
    spendSubsequent: false,
    directSocket: true,
    childTool: false,
    tlsPeerVerified: false,
    hostDrop: support === "supported",
  };
}

const PATHS = {
  app_fetch: app(
    "app_fetch",
    "supported",
    { seesHttp: true, redactMaterialized: true, sizeGate: true, spendSubsequent: true },
    "interceptor.cjs wrapFetch / globalThis.fetch",
  ),
  app_undici: app(
    "app_undici",
    "supported",
    { seesHttp: true, redactMaterialized: true, sizeGate: true, spendSubsequent: true },
    "interceptor.cjs undici fetch, request, dispatch, stream, pipeline, connect, upgrade",
  ),
  app_node_http: app(
    "app_node_http",
    "supported",
    { seesHttp: true, redactMaterialized: true, sizeGate: true, spendSubsequent: true },
    "interceptor.cjs http/https request and ClientRequest",
  ),
  app_node_http2: app(
    "app_node_http2",
    "partial",
    { seesHttp: true, redactMaterialized: true, sizeGate: true, spendSubsequent: true },
    "interceptor.cjs http2.connect / session.request / write-chunk redact",
  ),
  app_node_net: app(
    "app_node_net",
    "partial",
    { directSocket: true, seesResolvedIp: false },
    "interceptor.cjs net.Socket.connect host block; no payload redact",
  ),
  app_node_tls: app(
    "app_node_tls",
    "partial",
    { directSocket: true },
    "interceptor.cjs tls.connect host block; peer certificate is not a verified destination",
  ),
  app_websocket: app(
    "app_websocket",
    "partial",
    { seesHttp: false, sizeGate: true },
    "interceptor.cjs WebSocket host block and frame size; payloads are not parsed",
  ),
  app_connect_tunnel: app(
    "app_connect_tunnel",
    "partial",
    { sizeGate: true },
    "interceptor.cjs CONNECT tunnel writes; payloads are not parsed",
  ),
  app_child_tool: app(
    "app_child_tool",
    "partial",
    { seesHttp: true, childTool: true, redactMaterialized: true, sizeGate: true },
    "interceptor.cjs child_process curl, wget, httpie, aria2c; inline argv only",
  ),
  app_python_http: app(
    "app_python_http",
    "supported",
    { seesHttp: true, redactMaterialized: true, sizeGate: true, spendSubsequent: true },
    "sitecustomize.py plus agent SDK urllib/requests/httpx/aiohttp when installed",
  ),
  app_python_socket: app(
    "app_python_socket",
    "partial",
    { directSocket: true },
    "agent SDK socket.connect / connect_ex host block; no HTTP method",
  ),
  app_browser: app(
    "app_browser",
    "unsupported",
    {},
    "interceptor.cjs header: browsers stay outside the wrap",
  ),
  app_quic: app(
    "app_quic",
    "unsupported",
    {},
    "not named by the interceptor header or the Python wrap",
  ),
  app_raw_syscall: app(
    "app_raw_syscall",
    "gap",
    {},
    "application-path bypass; the wrap does not see a raw syscall",
  ),
  host_tc_enrolled: host(
    "host_tc_enrolled",
    "supported",
    "coverage matrix scoped-tc-drop-wsl2 is OBSERVED_FROM_REPOSITORY_EVIDENCE; this force does not execute it",
  ),
  host_cgroup_skb: host(
    "host_cgroup_skb",
    "partial",
    "coverage matrix: enroll-watch does not auto-attach cgroup_skb/egress to pod cgroups",
  ),
  host_uprobe_tls: host(
    "host_uprobe_tls",
    "partial",
    "coverage matrix: TLS uprobe observe with byte counts; observation is not a drop",
  ),
  host_not_enrolled: host(
    "host_not_enrolled",
    "unsupported",
    "protection state not_enrolled; no host enforce claim",
  ),
  host_managed_cloud: host(
    "host_managed_cloud",
    "unsupported",
    "product spec keeps GKE/EKS/AKS as TARGET_DESIGN; not a proof path",
  ),
};

PATHS.host_uprobe_tls.hostDrop = false;

function resolvePath(pathInput) {
  if (!pathInput || typeof pathInput !== "object" || Array.isArray(pathInput)) return null;
  const id = pathInput.id;
  if (typeof id !== "string" || !Object.prototype.hasOwnProperty.call(PATHS, id)) return null;
  return PATHS[id];
}

function listPaths() {
  return Object.keys(PATHS);
}

module.exports = {
  PATHS,
  listPaths,
  resolvePath,
};
