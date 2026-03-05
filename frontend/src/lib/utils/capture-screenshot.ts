import { toPng } from 'html-to-image';

interface ScreenshotOptions {
  includeLegend: boolean;
  includeSidebar: boolean;
  pixelRatio?: number;
}

/**
 * Replace <use> sprite references with inlined symbol content so that
 * html-to-image can serialize them. Also resolves currentColor to the
 * computed color value. Returns a function that restores the original DOM.
 * This is a patch until we have time to render the legend svg's as their own
 * components with @svgr/webpack
 */
function inlineSvgUseElements(root: HTMLElement): () => void {
  const restoreFns: (() => void)[] = [];

  root.querySelectorAll<SVGSVGElement>('svg.fill-current').forEach((svg) => {
    const useEl = svg.querySelector('use');
    if (!useEl) return;
    const href =
      useEl.getAttribute('href') ?? useEl.getAttributeNS('http://www.w3.org/1999/xlink', 'href');
    if (!href) return;

    const symbol = document.getElementById(href.replace(/^#/, ''));
    if (!symbol) return;

    const computedColor = getComputedStyle(svg).color;
    const group = document.createElementNS('http://www.w3.org/2000/svg', 'g');

    Array.from(symbol.children).forEach((child) => {
      const clone = child.cloneNode(true) as SVGElement;
      resolveCurrentColor(clone, computedColor);
      group.appendChild(clone);
    });

    svg.replaceChild(group, useEl);
    restoreFns.push(() => svg.replaceChild(useEl, group));
  });

  return () => restoreFns.forEach((fn) => fn());
}

function resolveCurrentColor(el: SVGElement, color: string): void {
  for (const attr of ['fill', 'stroke', 'stop-color', 'flood-color']) {
    if (el.getAttribute(attr) === 'currentColor') {
      el.setAttribute(attr, color);
    }
  }
  Array.from(el.children).forEach((child) => {
    if (child instanceof SVGElement) resolveCurrentColor(child, color);
  });
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
  const { includeLegend, includeSidebar, pixelRatio = 2 } = options;

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

  const restoreMapSvgs = inlineSvgUseElements(mapEl);
  try {
    mapDataUrl = await toPng(mapEl, { cacheBust: true, pixelRatio });

    if (includeSidebar) {
      const sidebarEl = document.querySelector<HTMLElement>('[data-screenshot="sidebar"]');
      if (sidebarEl) {
        sidebarDataUrl = await toPng(sidebarEl, { cacheBust: true, pixelRatio });
      }
    }
  } finally {
    restoreMapSvgs();
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
    const logoSize = 40 * pixelRatio;
    const padding = 16 * pixelRatio;
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
