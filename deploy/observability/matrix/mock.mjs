import { appendFileSync } from "node:fs";
import http from "node:http";
import zlib from "node:zlib";

const file = process.argv[2];
const port = Number(process.argv[3]);
const server = http.createServer((req, res) => {
  const chunks = [];
  req.on("data", (chunk) => chunks.push(chunk));
  req.on("end", () => {
    let body = Buffer.concat(chunks);
    const encoding = String(req.headers["content-encoding"] || "");
    if (encoding.includes("gzip")) {
      try {
        body = zlib.gunzipSync(body);
      } catch {
        /* keep raw */
      }
    }
    appendFileSync(file, `${JSON.stringify({ url: req.url, body: body.toString("utf8") })}\n`);
    res.writeHead(200, { "content-type": "application/json" });
    res.end("{}");
  });
});
server.listen(port, "0.0.0.0");
