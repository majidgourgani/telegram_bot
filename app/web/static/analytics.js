// Self-contained canvas charts — no external dependencies (works offline / CSP-safe).
(function () {
  const dataEl = document.getElementById("analytics-data");
  if (!dataEl) return;
  const data = JSON.parse(dataEl.textContent);

  const css = getComputedStyle(document.documentElement);
  const accent = (css.getPropertyValue("--accent") || "#4f7cff").trim();
  const accent2 = (css.getPropertyValue("--accent-2") || "#22b8a6").trim();
  const grid = (css.getPropertyValue("--border") || "#e4e7ee").trim();
  const text = (css.getPropertyValue("--muted") || "#6b7280").trim();

  function setup(canvas) {
    const ratio = window.devicePixelRatio || 1;
    const rect = canvas.getBoundingClientRect();
    const w = rect.width || canvas.parentElement.clientWidth;
    const h = canvas.height;
    canvas.width = w * ratio;
    canvas.height = h * ratio;
    const ctx = canvas.getContext("2d");
    ctx.scale(ratio, ratio);
    return { ctx, w, h };
  }

  function drawAxes(ctx, w, h, pad, maxY, steps) {
    ctx.strokeStyle = grid;
    ctx.fillStyle = text;
    ctx.lineWidth = 1;
    ctx.font = "11px system-ui, sans-serif";
    for (let i = 0; i <= steps; i++) {
      const y = pad.top + (h - pad.top - pad.bottom) * (i / steps);
      const val = Math.round(maxY - (maxY * i) / steps);
      ctx.beginPath();
      ctx.moveTo(pad.left, y);
      ctx.lineTo(w - pad.right, y);
      ctx.stroke();
      ctx.fillText(String(val), 6, y + 3);
    }
  }

  // --- Line: responses over time ---
  const lineCanvas = document.getElementById("dailyChart");
  if (lineCanvas && data.daily) {
    const { ctx, w, h } = setup(lineCanvas);
    const pad = { top: 12, right: 12, bottom: 24, left: 30 };
    const pts = data.daily;
    const maxY = Math.max(1, ...pts.map((p) => p.count));
    drawAxes(ctx, w, h, pad, maxY, Math.min(maxY, 4));
    if (pts.length) {
      const innerW = w - pad.left - pad.right;
      const innerH = h - pad.top - pad.bottom;
      const x = (i) => pad.left + (pts.length === 1 ? innerW / 2 : (innerW * i) / (pts.length - 1));
      const y = (v) => pad.top + innerH * (1 - v / maxY);
      ctx.strokeStyle = accent;
      ctx.lineWidth = 2;
      ctx.beginPath();
      pts.forEach((p, i) => (i ? ctx.lineTo(x(i), y(p.count)) : ctx.moveTo(x(i), y(p.count))));
      ctx.stroke();
      ctx.fillStyle = accent;
      pts.forEach((p, i) => {
        ctx.beginPath();
        ctx.arc(x(i), y(p.count), 3, 0, Math.PI * 2);
        ctx.fill();
      });
    } else {
      ctx.fillText("No data in range", w / 2 - 40, h / 2);
    }
  }

  // --- Bars: average score by area ---
  const areaCanvas = document.getElementById("areaChart");
  if (areaCanvas && data.areas) {
    const { ctx, w, h } = setup(areaCanvas);
    const pad = { top: 12, right: 12, bottom: 40, left: 30 };
    const bars = data.areas;
    const maxY = 10;
    drawAxes(ctx, w, h, pad, maxY, 5);
    const innerW = w - pad.left - pad.right;
    const innerH = h - pad.top - pad.bottom;
    const bw = bars.length ? Math.min(70, (innerW / bars.length) * 0.6) : 0;
    ctx.textAlign = "center";
    bars.forEach((b, i) => {
      const cx = pad.left + (innerW * (i + 0.5)) / bars.length;
      const bh = innerH * (b.avg / maxY);
      ctx.fillStyle = i % 2 ? accent2 : accent;
      ctx.fillRect(cx - bw / 2, pad.top + innerH - bh, bw, bh);
      ctx.fillStyle = text;
      ctx.fillText(b.name, cx, h - 22);
      ctx.fillText(b.avg.toFixed(2), cx, pad.top + innerH - bh - 6);
    });
    ctx.textAlign = "start";
  }

  // --- Horizontal funnel ---
  const funnelCanvas = document.getElementById("funnelChart");
  if (funnelCanvas && data.funnel) {
    const { ctx, w, h } = setup(funnelCanvas);
    const stages = [
      ["Started", data.funnel.started],
      ["Consented", data.funnel.consented],
      ["Completed", data.funnel.completed],
    ];
    const maxV = Math.max(1, ...stages.map((s) => s[1]));
    const rowH = 24;
    const gap = 8;
    const labelW = 90;
    ctx.font = "12px system-ui, sans-serif";
    stages.forEach((s, i) => {
      const y = i * (rowH + gap) + 4;
      const bw = (w - labelW - 50) * (s[1] / maxV);
      ctx.fillStyle = text;
      ctx.fillText(s[0], 0, y + rowH / 2 + 4);
      ctx.fillStyle = i === 2 ? accent2 : accent;
      ctx.fillRect(labelW, y, Math.max(bw, 2), rowH);
      ctx.fillStyle = text;
      ctx.fillText(String(s[1]), labelW + Math.max(bw, 2) + 8, y + rowH / 2 + 4);
    });
  }
})();
