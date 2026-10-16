/**
 * Observe and opt-in in-process gates.
 * Nothing here listens on a socket or spawns a process.
 */

import { PassThrough, Transform, Writable } from "node:stream";
import { createFramer } from "./parse.js";

export function tapReadable(readable, onChunk) {
  if (readable && typeof readable.getReader === "function" && typeof readable.on !== "function") {
    return { ok: false, reason: "web_stream" };
  }
  if (!readable || typeof readable.on !== "function" || typeof readable.listenerCount !== "function") {
    return { ok: false, reason: "not_flowing" };
  }
  if (readable.readableFlowing !== true || readable.listenerCount("data") < 1) {
    return { ok: false, reason: "not_flowing" };
  }
  const handler = (chunk) => {
    try {
      onChunk(chunk);
    } catch {
      onChunk(null);
    }
  };
  readable.on("data", handler);
  return {
    ok: true,
    close() {
      readable.off("data", handler);
    },
  };
}

export function createInProcessGate(transport, onFrame) {
  const framer = createFramer(transport);
  return new Transform({
    transform(chunk, _enc, cb) {
      deliver(framer.push(chunk), onFrame, (raw) => this.push(raw));
      cb();
    },
    flush(cb) {
      deliver(framer.finish(), onFrame, (raw) => this.push(raw));
      cb();
    },
  });
}

function deliver(frames, onFrame, push) {
  for (const fr of frames) {
    let decision;
    try {
      decision = onFrame(fr);
    } catch {
      decision = { forward: false };
    }
    if (decision && decision.forward && fr.raw && fr.raw.length) push(fr.raw);
  }
}

export function createStdioPairGate({ fromChild, toChild, onClientFrame, onServerFrame }) {
  const clientFramer = createFramer("stdio");
  const serverFramer = createFramer("stdio");
  const stdout = new PassThrough();
  const queued = [];
  let inboundPartial = false;

  function flushErrors() {
    if (inboundPartial) return;
    while (queued.length) stdout.write(queued.shift());
  }

  function accept(frames, onFrame, writeForward) {
    for (const fr of frames) {
      let decision;
      try {
        decision = onFrame(fr);
      } catch {
        decision = { forward: false };
      }
      if (decision && decision.forward && fr.raw && fr.raw.length && writeForward) writeForward(fr.raw);
      if (decision && decision.replacement) queued.push(decision.replacement);
    }
  }

  const stdin = new Writable({
    write(chunk, _enc, cb) {
      accept(clientFramer.push(chunk), onClientFrame, (raw) => {
        try {
          toChild.write(raw);
        } catch {
          /* the child stream is the caller's; a write failure is not a policy allow */
        }
      });
      flushErrors();
      cb();
    },
    final(cb) {
      accept(clientFramer.finish(), onClientFrame, (raw) => {
        toChild.write(raw);
      });
      flushErrors();
      cb();
    },
  });

  function onChild(chunk) {
    const frames = serverFramer.push(chunk);
    inboundPartial = serverFramer.buffered() > 0;
    accept(frames, onServerFrame, (raw) => stdout.write(raw));
    inboundPartial = serverFramer.buffered() > 0;
    flushErrors();
  }

  fromChild.on("data", onChild);
  return {
    stdin,
    stdout,
    close() {
      fromChild.off("data", onChild);
    },
  };
}
