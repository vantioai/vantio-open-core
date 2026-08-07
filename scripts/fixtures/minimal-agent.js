// Minimal agent for Sight Loop offline prove — one synthetic LLM-shaped HTTP call.
// Used by scripts/sight-loop-prove.sh (no real API key or network required).

const port = process.env.VANTIO_MOCK_LLM_PORT;
if (!port) {
  console.error("VANTIO_MOCK_LLM_PORT is required");
  process.exit(1);
}

const url = `http://127.0.0.1:${port}/v1/chat/completions`;

(async () => {
  const res = await fetch(url, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ model: "sight-loop-fixture", messages: [{ role: "user", content: "hi" }] }),
  });

  if (!res.ok) {
    console.error(`fixture fetch failed: ${res.status}`);
    process.exit(1);
  }

  await res.text();
  console.log("sight-loop fixture agent finished");
})();
