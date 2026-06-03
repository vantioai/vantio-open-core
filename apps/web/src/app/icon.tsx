import { ImageResponse } from "next/og";

export const size = { width: 512, height: 512 };
export const contentType = "image/png";

// Branded ∅ mark drawn with CSS shapes (a ring + diagonal slash) instead of a
// font glyph, so it never depends on a dynamically downloaded font. Also used
// as the Organization logo in JSON-LD and the PWA manifest icon.
export default function Icon() {
  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          backgroundColor: "#030305",
        }}
      >
        <div
          style={{
            position: "relative",
            display: "flex",
            width: 300,
            height: 300,
            alignItems: "center",
            justifyContent: "center",
          }}
        >
          <div style={{ width: 236, height: 236, borderRadius: 9999, border: "32px solid #00e87a" }} />
          <div
            style={{
              position: "absolute",
              left: -10,
              top: 134,
              width: 320,
              height: 32,
              borderRadius: 9999,
              backgroundColor: "#00e87a",
              transform: "rotate(-45deg)",
            }}
          />
        </div>
      </div>
    ),
    { ...size }
  );
}
