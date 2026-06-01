import { ImageResponse } from "next/og";

export const size = { width: 512, height: 512 };
export const contentType = "image/png";

// Branded ∅ app icon — also referenced as the Organization logo in JSON-LD
// and the PWA manifest icon.
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
          color: "#00e87a",
          fontSize: 360,
          fontWeight: 900,
          fontFamily: "Arial, sans-serif",
        }}
      >
        ∅
      </div>
    ),
    { ...size }
  );
}
