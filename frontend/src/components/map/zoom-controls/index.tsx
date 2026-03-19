import { useMap } from 'react-map-gl';

import { useAtomValue } from 'jotai';
import { Minus, Plus } from 'lucide-react';
import { useTranslations } from 'next-intl';

import { Button } from '@/components/ui/button';
import { screenshotOpenAtom } from '@/containers/map/store';
import { FCWithMessages } from '@/types';

const BUTTON_CLASSES = 'group bg-white';
const ICON_CLASSES = 'h-4 w-4 text-black group-hover:text-white';

const ZoomControls: FCWithMessages = () => {
  const t = useTranslations('components.map');
  const screenshotOpen = useAtomValue(screenshotOpenAtom);

  const {
    current: { getZoom, zoomTo, getMinZoom, getMaxZoom },
  } = useMap();

  const zoom = getZoom();
  const minZoom = getMinZoom();
  const maxZoom = getMaxZoom();

  if (screenshotOpen) return null;

  return (
    <div className="absolute right-0 top-0 z-10 flex flex-col border border-r-0 border-t-0 border-black">
      <Button
        type="button"
        size="icon"
        disabled={zoom === maxZoom}
        onClick={() => zoomTo(Math.round(Math.min(zoom + 1, maxZoom)), { duration: 250 })}
        className={BUTTON_CLASSES}
      >
        <Plus className={ICON_CLASSES} aria-hidden />
        <span className="sr-only">{t('zoom-in')}</span>
      </Button>
      <Button
        type="button"
        size="icon"
        onClick={() => zoomTo(Math.round(Math.max(zoom - 1, minZoom)), { duration: 250 })}
        disabled={zoom === minZoom}
        className={BUTTON_CLASSES}
      >
        <Minus className={ICON_CLASSES} aria-hidden />
        <span className="sr-only">{t('zoom-out')}</span>
      </Button>
    </div>
  );
};

ZoomControls.messages = ['components.map'];

export default ZoomControls;
