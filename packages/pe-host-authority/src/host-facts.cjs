"use strict";

const fs = require("node:fs");

function capHex(status, name) {
  const match = status.match(new RegExp(`^${name}:\\s*([0-9a-fA-F]+)$`, "m"));
  return match ? match[1].toLowerCase() : null;
}

function collectHostFacts() {
  const status = fs.readFileSync("/proc/self/status", "utf8");
  const euid = typeof process.geteuid === "function" ? process.geteuid() : null;
  const capEff = capHex(status, "CapEff");
  const capPrm = capHex(status, "CapPrm");
  let bpfPresent = false;
  let bpfWritable = false;
  let bpfListable = false;
  let bpfError = null;
  try {
    fs.accessSync("/sys/fs/bpf", fs.constants.F_OK);
    bpfPresent = true;
  } catch (error) {
    bpfError = error.code || "ABSENT";
  }
  if (bpfPresent) {
    try {
      fs.accessSync("/sys/fs/bpf", fs.constants.W_OK);
      bpfWritable = true;
    } catch (error) {
      bpfError = error.code || "EACCES";
    }
    try {
      fs.readdirSync("/sys/fs/bpf");
      bpfListable = true;
    } catch {
      bpfListable = false;
    }
  }
  return {
    euid,
    cap_eff: capEff,
    cap_prm: capPrm,
    cap_eff_zero: capEff === "0000000000000000",
    cap_prm_zero: capPrm === "0000000000000000",
    bpf_mount_present: bpfPresent,
    bpf_writable_by_this_euid: bpfWritable,
    bpf_listable_by_this_euid: bpfListable,
    bpf_access_error: bpfWritable ? null : bpfError,
    kernel_loaded_this_force: false,
    loader_mutated_this_force: false,
    privileged_helper_invoked: false,
    clean_host_infrastructure: false,
    pins_created_by_this_force: false,
  };
}

module.exports = {
  collectHostFacts,
};
