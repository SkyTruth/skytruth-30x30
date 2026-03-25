import { toPng } from 'html-to-image';

const isFirefox = typeof navigator !== 'undefined' && /firefox/i.test(navigator.userAgent);

interface ScreenshotOptions {
  includeLegend: boolean;
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
  const { includeLegend, pixelRatio = 2 } = options;

  const mapEl = document.querySelector<HTMLElement>('[data-screenshot="map"]');
  if (!mapEl) throw new Error('Map element not found');

  // The screenshot component ensures the legend is open via atom before calling this.
  // Here we just hide it with CSS if the user unchecked "include legend",
  // or expand the scroll container to fit content (up to map height) if included.
  const legendEl = document.querySelector<HTMLElement>('[data-screenshot="legend"]');
  const legendScrollContainer = legendEl?.querySelector<HTMLElement>('.overflow-y-auto');

  const prevLegendVisibility = legendEl?.style.visibility ?? '';
  const prevScrollStyle = legendScrollContainer?.style.cssText ?? '';

  if (!includeLegend && legendEl) {
    legendEl.style.visibility = 'hidden';
  } else if (includeLegend && legendScrollContainer) {
    const mapHeight = mapEl.offsetHeight;
    legendScrollContainer.style.maxHeight = `${mapHeight}px`;
    legendScrollContainer.style.height = 'auto';
    legendScrollContainer.style.overflow = 'hidden';
  }

  let mapDataUrl: string;

  // isFirefox check is a temporary patch until
  // https://github.com/bubkoo/html-to-image/issues/508
  // is resolved.
  const toPngOptions = {
    cacheBust: true,
    pixelRatio,
    ...(isFirefox && { skipFonts: true }),
  };

  // Minimum data URL length that indicates a non-blank capture.
  // A blank canvas produces a very short data URL, while a real
  // map capture is significantly larger. This is a patch for Safari
  // which clears the drawing buffer often which can result in toDataUrl()
  // not capturing the fully drawn canvas
  const MIN_DATA_URL_LENGTH = 250_000;
  const MAX_RETRIES = 3;
  const RETRY_DELAY_MS = 200;

  const restoreMapSvgs = inlineSvgUseElements(mapEl);
  try {
    mapDataUrl = await toPng(mapEl, toPngOptions);

    let attempts = 0;
    while (mapDataUrl.length < MIN_DATA_URL_LENGTH && attempts < MAX_RETRIES) {
      await new Promise((r) => setTimeout(r, RETRY_DELAY_MS));
      mapDataUrl = await toPng(mapEl, toPngOptions);
      attempts++;
    }
  } finally {
    restoreMapSvgs();
    if (!includeLegend && legendEl) {
      legendEl.style.visibility = prevLegendVisibility;
    }
    if (legendScrollContainer) {
      legendScrollContainer.style.cssText = prevScrollStyle;
    }
  }

  // Load captured images
  const mapImg = await loadImage(mapDataUrl);

  const canvas = document.createElement('canvas');
  canvas.width = mapImg.width;
  canvas.height = mapImg.height;

  const ctx = canvas.getContext('2d')!;

  ctx.drawImage(mapImg, 0, 0);

  // Draw SkyTruth logo in top-left of the map area
  try {
    const logo = await loadImage('/images/SkyTruth_logo.svg');
    const logoRatio = 2.92 / 2; // Asepct ratio of skytruth logo
    const logoHeight = 120 * pixelRatio;
    const logoWidth = logoHeight * logoRatio;
    const padding = 16 * pixelRatio;
    ctx.drawImage(logo, padding, padding, logoWidth, logoHeight);
  } catch {
    // Logo not found — skip silently
  }

  return canvas.toDataURL('image/png');
}

export function downloadScreenshot(dataUrl: string): void {
  const now = new Date();
  const date = `${now.getMonth() + 1}_${now.getDate()}_${now.getFullYear()}`;
  const hours = now.getHours();
  const minutes = now.getMinutes().toString().padStart(2, '0');
  const seconds = now.getSeconds().toString().padStart(2, '0');
  const period = hours >= 12 ? 'PM' : 'AM';
  const hours12 = hours % 12 || 12;
  const time = `${hours12}_${minutes}_${seconds} ${period}`;

  const a = document.createElement('a');
  a.href = dataUrl;
  a.download = `SkyTruth 30x30 Screenshot ${date}, ${time}.png`;
  a.click();
}
