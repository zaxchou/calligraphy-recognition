import React, { useState } from "react";
import { createRoot } from "react-dom/client";
import EmotionOrb from "./EmotionOrb";
import { emotionLabel } from "./emotion-utils";

function App() {
  const [value, setValue] = useState(0.0);

  return (
    <div
      style={{
        minHeight: "100vh",
        margin: 0,
        background: "radial-gradient(circle at 50% 40%, #15151f 0%, #07070b 70%)",
        color: "#eee",
        fontFamily: "system-ui, -apple-system, Segoe UI, Roboto, sans-serif",
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        gap: 28,
      }}
    >
      <div style={{ width: "min(86vmin, 560px)", height: "min(86vmin, 560px)", position: "relative" }}>
        <EmotionOrb value={value} />
      </div>

      <div style={{ textAlign: "center", userSelect: "none" }}>
        <div style={{ fontSize: 30, fontWeight: 600, letterSpacing: 2 }}>
          {emotionLabel(value)}
        </div>
        <div
          style={{
            fontSize: 15,
            opacity: 0.7,
            marginTop: 6,
            fontVariantNumeric: "tabular-nums",
          }}
        >
          情绪值 v = {value.toFixed(3)}&nbsp;&nbsp;（-1.000 愤怒 → +1.000 快乐）
        </div>
      </div>

      <input
        type="range"
        min={-1}
        max={1}
        step={0.001}
        value={value}
        onChange={(e) => setValue(parseFloat(e.target.value))}
        style={{ width: "min(86vmin, 560px)", accentColor: "#7C3AED" }}
      />
    </div>
  );
}

createRoot(document.getElementById("root")).render(<App />);
