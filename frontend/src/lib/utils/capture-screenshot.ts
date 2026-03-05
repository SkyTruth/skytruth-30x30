import { toPng } from 'html-to-image';

interface ScreenshotOptions {
  includeLegend: boolean;
  includeSidebar: boolean;
}

function loadImage(src: string): Promise<HTMLImageElement> {
  return new Promise((resolve, reject) => {
    const img = new Image();
    img.onload = () => resolve(img);
    img.onerror = reject;
    img.src = src;
  });
}

export async function buildScreenshotDataUrl(options: ScreenshotOptions): Promise<string> {
  const { includeLegend, includeSidebar } = options;

  const mapEl = document.querySelector<HTMLElement>('[data-screenshot="map"]');
  if (!mapEl) throw new Error('Map element not found');

  // Temporarily hide legend if excluded
  const legendEl = document.querySelector<HTMLElement>('[data-screenshot="legend"]');
  const legendPrevVisibility = legendEl?.style.visibility ?? '';
  if (!includeLegend && legendEl) {
    legendEl.style.visibility = 'hidden';
  }

  let mapDataUrl: string;
  let sidebarDataUrl: string | null = null;

  try {
    mapDataUrl = await toPng(mapEl, { cacheBust: true });

    if (includeSidebar) {
      const sidebarEl = document.querySelector<HTMLElement>('[data-screenshot="sidebar"]');
      if (sidebarEl) {
        sidebarDataUrl = await toPng(sidebarEl, { cacheBust: true });
      }
    }
  } finally {
    // Restore legend visibility
    if (!includeLegend && legendEl) {
      legendEl.style.visibility = legendPrevVisibility;
    }
  }

  // Load captured images
  const mapImg = await loadImage(mapDataUrl);
  const sidebarImg = sidebarDataUrl ? await loadImage(sidebarDataUrl) : null;

  // Composite onto a single canvas
  const sidebarWidth = sidebarImg ? sidebarImg.width : 0;
  const totalWidth = sidebarWidth + mapImg.width;
  const totalHeight = Math.max(mapImg.height, sidebarImg ? sidebarImg.height : 0);

  const canvas = document.createElement('canvas');
  canvas.width = totalWidth;
  canvas.height = totalHeight;

  const ctx = canvas.getContext('2d')!;

  if (sidebarImg) {
    ctx.drawImage(sidebarImg, 0, 0);
  }
  ctx.drawImage(mapImg, sidebarWidth, 0);

  // Draw SkyTruth logo in top-left of the map area
  try {
    const logo = await loadImage('/images/skytruth-30-30-logo.svg');
    const logoSize = 40;
    const padding = 16;
    ctx.drawImage(logo, sidebarWidth + padding, padding, logoSize, logoSize);
  } catch {
    // Logo not found — skip silently
  }

  return canvas.toDataURL('image/png');
}

export function downloadScreenshot(dataUrl: string): void {
  const a = document.createElement('a');
  a.href = dataUrl;
  a.download = 'map-screenshot.png';
  a.click();
}
