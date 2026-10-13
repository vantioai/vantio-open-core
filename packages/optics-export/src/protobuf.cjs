"use strict";

function varint(value) {
  let v = BigInt(value);
  const out = [];
  while (v > 127n) {
    out.push(Number((v & 127n) | 128n));
    v >>= 7n;
  }
  out.push(Number(v));
  return Buffer.from(out);
}

function key(field, wire) {
  return varint((field << 3) | wire);
}

function bytesField(field, buf) {
  return Buffer.concat([key(field, 2), varint(buf.length), buf]);
}

function stringField(field, text) {
  return bytesField(field, Buffer.from(String(text), "utf8"));
}

function varintField(field, value) {
  return Buffer.concat([key(field, 0), varint(value)]);
}

function fixed64Field(field, value) {
  const buf = Buffer.alloc(8);
  let v = BigInt(value);
  for (let i = 0; i < 8; i += 1) {
    buf[i] = Number(v & 255n);
    v >>= 8n;
  }
  return Buffer.concat([key(field, 1), buf]);
}

function messageField(field, buf) {
  return bytesField(field, buf);
}

module.exports = {
  bytesField,
  fixed64Field,
  messageField,
  stringField,
  varintField,
};
