import { ImageResponse } from "next/og";
import { SITE } from "@/lib/seo";

export const alt = SITE.defaultTitle;
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";

// Branded 1200x630 social share card. Used as og:image and (via twitter-image)
// twitter:image for every route that doesn't define its own.
export default function OpengraphImage() {
  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          flexDirection: "column",
          justifyContent: "space-between",
          padding: "72px",
          backgroundColor: "#030305",
          backgroundImage:
            "radial-gradient(ellipse 90% 60% at 50% -10%, rgba(0,232,122,0.18) 0%, rgba(3,3,5,0) 70%)",
          color: "#e8e8f0",
          fontFamily: "Arial, sans-serif",
        }}
      >
        <div style={{ display: "flex", alignItems: "center" }}>
          <div
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              width: 64,
              height: 64,
              borderRadius: 16,
              backgroundColor: "rgba(0,232,122,0.12)",
            }}
          >
            <div
              style={{
                position: "relative",
                display: "flex",
                width: 40,
                height: 40,
                alignItems: "center",
                justifyContent: "center",
              }}
            >
              <div style={{ width: 28, height: 28, borderRadius: 9999, border: "5px solid #00e87a" }} />
              <div
                style={{
                  position: "absolute",
                  left: 2,
                  top: 17,
                  width: 36,
                  height: 5,
                  borderRadius: 9999,
                  backgroundColor: "#00e87a",
                  transform: "rotate(-45deg)",
                }}
              />
            </div>
          </div>
          <div
            style={{
              marginLeft: 20,
              fontSize: 30,
              fontWeight: 700,
              letterSpacing: 6,
              color: "#e8e8f0",
            }}
          >
            VANTIO
          </div>
        </div>

        <div style={{ display: "flex", flexDirection: "column" }}>
          <div
            style={{
              display: "flex",
              fontSize: 68,
              fontWeight: 800,
              lineHeight: 1.1,
              letterSpacing: -1,
              maxWidth: 980,
            }}
          >
            Go fully autonomous. Stay fully compliant.
          </div>
          <div
            style={{
              display: "flex",
              marginTop: 28,
              fontSize: 30,
              color: "#6b6b8a",
              maxWidth: 920,
            }}
          >
            Regulated AI governance that secures your agents and accelerates deployment.
          </div>
        </div>

        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
          <div style={{ display: "flex", fontSize: 26, color: "#00e87a", fontWeight: 600 }}>
            vantio.ai
          </div>
          <div style={{ display: "flex", fontSize: 24, color: "#6b6b8a" }}>
            Regulated AI governance
          </div>
        </div>
      </div>
    ),
    { ...size }
  );
}
