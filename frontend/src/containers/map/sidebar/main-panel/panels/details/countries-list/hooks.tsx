import { useCallback, useLayoutEffect, useRef, useState, useEffect } from 'react';

export function useNeedsTruncate<T extends HTMLElement>(
  maxRows: number,
  rowHeightPx: number,
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  deps: any[] = []
) {
  const containerRef = useRef<T>(null);
  const [needsTruncate, setNeedsTruncate] = useState(false);

  const measure = useCallback(() => {
    const cotaniner = containerRef.current;
    if (!cotaniner) return;

    const allowed = rowHeightPx * maxRows;
    setNeedsTruncate(cotaniner.scrollHeight > allowed + 1);
  }, [containerRef, maxRows, rowHeightPx]);

  useLayoutEffect(() => {
    measure();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [maxRows, measure, rowHeightPx, ...deps]);

  useEffect(() => {
    const cotaniner = containerRef.current;
    if (!cotaniner) return;

    const ro = new ResizeObserver(measure);
    ro.observe(cotaniner);

    const mo = new MutationObserver(measure);
    mo.observe(cotaniner, { childList: true, subtree: true, characterData: true });

    return () => {
      ro.disconnect();
      mo.disconnect();
    };
  });

  return { containerRef, needsTruncate, remeasure: measure };
}
