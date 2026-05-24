import { useEffect, useRef } from 'react';

const CHANNELS = 4;
const CHANNEL_LABELS = ['Fp1', 'C3', 'Pz', 'O2'];

function eegSignal(t: number, ch: number): number {
  const alpha = 0.65 * Math.sin(2 * Math.PI * (9.5 + ch * 0.6) * t + ch * 0.9);
  const beta  = 0.22 * Math.sin(2 * Math.PI * (18 + ch * 1.4) * t + ch * 1.7);
  const theta = 0.30 * Math.sin(2 * Math.PI * (5.5 + ch * 0.3) * t + ch * 2.4);
  const drift = 0.12 * Math.sin(2 * Math.PI * 0.07 * t + ch * 0.6);
  return alpha + beta + theta + drift;
}

export default function HeroEEG() {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d')!;

    let animId: number;
    let t = 0;
    const TIME_PER_PX = 0.0018;
    const AMPLITUDE = 34;

    function resize() {
      if (!canvas) return;
      canvas.width  = canvas.offsetWidth;
      canvas.height = canvas.offsetHeight;
    }

    function draw() {
      if (!canvas) return;
      const { width, height } = canvas;
      ctx.clearRect(0, 0, width, height);

      const step = 2;

      for (let ch = 0; ch < CHANNELS; ch++) {
        const centerY = height * ((ch + 1) / (CHANNELS + 1));

        // Baseline
        ctx.beginPath();
        ctx.strokeStyle = 'rgba(0, 87, 255, 0.08)';
        ctx.lineWidth = 1;
        ctx.moveTo(0, centerY);
        ctx.lineTo(width, centerY);
        ctx.stroke();

        // Channel label
        ctx.font = `10px 'SF Mono', monospace`;
        ctx.fillStyle = 'rgba(0, 87, 255, 0.3)';
        ctx.fillText(CHANNEL_LABELS[ch], 16, centerY - AMPLITUDE - 8);

        // Waveform
        ctx.beginPath();
        ctx.strokeStyle = 'rgba(0, 87, 255, 0.22)';
        ctx.lineWidth = 1.5;
        ctx.lineJoin = 'round';

        let first = true;
        for (let x = 0; x <= width; x += step) {
          const tAtX = t - (width - x) * TIME_PER_PX;
          const y = centerY + eegSignal(tAtX, ch) * AMPLITUDE;
          if (first) { ctx.moveTo(x, y); first = false; }
          else ctx.lineTo(x, y);
        }
        ctx.stroke();
      }

      t += 0.016;
      animId = requestAnimationFrame(draw);
    }

    const ro = new ResizeObserver(() => resize());
    ro.observe(canvas.parentElement!);
    resize();
    draw();

    return () => {
      cancelAnimationFrame(animId);
      ro.disconnect();
    };
  }, []);

  return (
    <canvas
      ref={canvasRef}
      style={{
        position: 'absolute',
        inset: 0,
        width: '100%',
        height: '100%',
        pointerEvents: 'none',
      }}
    />
  );
}
