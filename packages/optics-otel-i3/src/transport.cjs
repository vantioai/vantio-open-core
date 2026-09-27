"use strict";

const http = require("node:http");
const https = require("node:https");

function postOtlpJson(request) {
  const target = new URL(request.endpoint);
  const lib = target.protocol === "https:" ? https : http;
  const body = request.body;
  const timeoutMs = request.timeoutMs;
  return new Promise((resolve, reject) => {
    const req = lib.request({
      protocol: target.protocol,
      hostname: target.hostname,
      port: target.port === "" ? (target.protocol === "https:" ? 443 : 80) : target.port,
      path: target.pathname,
      method: "POST",
      agent: false,
      headers: {
        "content-type": "application/json",
        "content-length": Buffer.byteLength(body),
      },
    }, (res) => {
      res.resume();
      res.on("end", () => {
        resolve({ status: res.statusCode });
      });
    });
    req.setTimeout(timeoutMs, () => {
      req.destroy();
      const error = new Error("timeout");
      error.code = "TIMEOUT";
      reject(error);
    });
    req.on("error", (error) => {
      const wrapped = new Error("transport");
      wrapped.code = error && error.code ? error.code : "TRANSPORT";
      reject(wrapped);
    });
    req.end(body);
  });
}

module.exports = { postOtlpJson };
