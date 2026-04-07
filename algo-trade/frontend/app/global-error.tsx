"use client";

// Prevent static prerendering — avoids a workUnitAsyncStorage invariant in Next.js 16.1.6
export const dynamic = "force-dynamic";

export default function GlobalError({
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <html lang="en" className="dark">
      <body
        style={{
          display: "flex",
          minHeight: "100vh",
          alignItems: "center",
          justifyContent: "center",
          background: "#09090b",
          color: "#f4f4f5",
          fontFamily: "ui-sans-serif, system-ui, sans-serif",
          margin: 0,
        }}
      >
        <div style={{ textAlign: "center" }}>
          <p style={{ marginBottom: "12px", fontSize: "14px", color: "#a1a1aa" }}>
            Something went wrong
          </p>
          <button
            onClick={reset}
            style={{
              padding: "8px 16px",
              borderRadius: "8px",
              background: "#27272a",
              color: "#f4f4f5",
              border: "1px solid #3f3f46",
              cursor: "pointer",
              fontSize: "13px",
            }}
          >
            Try again
          </button>
        </div>
      </body>
    </html>
  );
}
