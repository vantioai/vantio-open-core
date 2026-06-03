import { ImageResponse } from "next/og";
import { getAllPosts, getPost } from "@/lib/brief";

export const alt = "The Brief — Vantio AI";
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";

export function generateStaticParams() {
  return getAllPosts().map((p) => ({ slug: p.slug }));
}

const ACCENT: Record<string, string> = {
  emerald: "#00e87a",
  blue: "#3b82f6",
  red: "#ef4444",
  violet: "#a78bfa",
  amber: "#fbbf24",
};

// Code-drawn gradient social card per post — no AI images.
export default async function Image({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const post = getPost(slug);
  const title = post?.title ?? "The Brief";
  const category = post?.category ?? "Insights";
  const accent = ACCENT[post?.cover ?? "emerald"] ?? "#00e87a";

  return new ImageResponse(
    (
      <div
        style={{
          height: "100%",
          width: "100%",
          display: "flex",
          flexDirection: "column",
          justifyContent: "space-between",
          background: "#0a0a12",
          padding: "72px",
          backgroundImage: `radial-gradient(900px 450px at 88% -10%, ${accent}26, transparent)`,
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: "16px" }}>
          <div
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              width: "52px",
              height: "52px",
              borderRadius: "14px",
              background: `${accent}22`,
              color: accent,
              fontSize: "34px",
              fontWeight: 900,
            }}
          >
            ∅
          </div>
          <div style={{ display: "flex", color: "#e8e8f0", fontSize: "26px", fontWeight: 700, letterSpacing: "3px" }}>
            VANTIO · THE BRIEF
          </div>
        </div>

        <div style={{ display: "flex", flexDirection: "column" }}>
          <div
            style={{
              display: "flex",
              color: accent,
              fontSize: "24px",
              fontWeight: 800,
              textTransform: "uppercase",
              letterSpacing: "5px",
              marginBottom: "22px",
            }}
          >
            {category}
          </div>
          <div style={{ display: "flex", color: "#e8e8f0", fontSize: "62px", fontWeight: 800, lineHeight: 1.08, maxWidth: "980px" }}>
            {title}
          </div>
        </div>

        <div style={{ display: "flex", color: "#a0a0ba", fontSize: "24px" }}>vantio.ai/brief</div>
      </div>
    ),
    { ...size }
  );
}
