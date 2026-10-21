import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react';

import { Popup, useMap } from 'react-map-gl';

import { useAtomValue, useSetAtom } from 'jotai';
import type { Popup as MapboxPopup, PopupOptions } from 'mapbox-gl';
import { useLocale, useTranslations } from 'next-intl';
import { useKey } from 'rooks';

import Icon from '@/components/ui/icon';
import {
  Select,
  SelectTrigger,
  SelectContent,
  SelectItem,
  SelectValue,
} from '@/components/ui/select';
import PopupItem from '@/containers/map/content/map/popup/item';
import { layersInteractiveAtom, popupAtom } from '@/containers/map/store';
import useLocationName from '@/hooks/use-location-name';
import { cn } from '@/lib/classnames';
import CloseIcon from '@/styles/icons/close.svg';
import { FCWithMessages } from '@/types';
import { useGetLayers } from '@/types/generated/layer';
import { InteractionConfig } from '@/types/layers';

import { useSyncMapLayers } from '../sync-settings';

import { EEZ_SOURCE, POPUP_ICON_BY_SOURCE, POPUP_PROPERTIES_BY_SOURCE } from './constants';

const PopupContainer: FCWithMessages = () => {
  const locale = useLocale();
  const t = useTranslations('containers.map');

  const popup = useAtomValue(popupAtom);
  const layersInteractive = useAtomValue(layersInteractiveAtom);

  const [syncedLayers] = useSyncMapLayers();

  const [selectedLayerSlug, setSelectedLayerSlug] = useState<string | null>(null);

  const setPopup = useSetAtom(popupAtom);

  const { default: mapRef } = useMap();
  const popupRef = useRef<MapboxPopup>(null);
  const [anchor, setAnchor] = useState<PopupOptions['anchor']>();

  // Change popup direction to minimize overlaps from panels
  useLayoutEffect(() => {
    const map = mapRef?.getMap();
    const mapboxPopup = popupRef.current;
    if (!map || !mapboxPopup) return;

    const updateAnchor = () => {
      const mapRect = map.getContainer().getBoundingClientRect();
      const { width, height } = mapboxPopup.getElement()!.getBoundingClientRect();
      const point = map.project(mapboxPopup.getLngLat());
      const cursor = { x: mapRect.left + point.x, y: mapRect.top + point.y };

      // The popup is above the cursor by default
      const popupTop = cursor.y - height;
      const popupBottom = cursor.y;

      // Popup moves around the edges of nearby panels to minimize overlaps
      const panels = Array.from(document.querySelectorAll('[data-map-overlay-panel]'))
        .map((panel) => panel.getBoundingClientRect())
        .filter((panel) => panel.top < popupBottom && panel.bottom > popupTop);

      // The nearest visible edge on each side of the cursor
      const leftEdge = Math.max(
        mapRect.left,
        ...panels.filter((panel) => panel.right <= cursor.x).map((panel) => panel.right)
      );
      const rightEdge = Math.min(
        mapRect.right,
        ...panels.filter((panel) => panel.left >= cursor.x).map((panel) => panel.left)
      );

      // A popup centered on the cursor needs half its width free on each side
      let side: 'left' | 'right' | null = null;
      if (cursor.x - leftEdge < width / 2) side = 'left';
      else if (rightEdge - cursor.x < width / 2) side = 'right';

      if (!side) {
        setAnchor(undefined);
        return;
      }

      // A popup needs half its height free above and below;
      // use a corner instead near the top or bottom of the map
      let corner = '';
      if (cursor.y - mapRect.top < height / 2) corner = 'top-';
      else if (mapRect.bottom - cursor.y < height / 2) corner = 'bottom-';

      setAnchor(`${corner}${side}` as PopupOptions['anchor']);
    };

    // The popup is added to the map after this component's layout effects run
    if (mapboxPopup.isOpen()) updateAnchor();
    else mapboxPopup.once('open', updateAnchor);
    map.on('move', updateAnchor);

    // Re-anchor as the panels open and close over the map
    const resizeObserver = new ResizeObserver(() => {
      if (mapboxPopup.isOpen()) updateAnchor();
    });
    document
      .querySelectorAll('[data-map-overlay-panel]')
      .forEach((panel) => resizeObserver.observe(panel));

    return () => {
      mapboxPopup.off('open', updateAnchor);
      map.off('move', updateAnchor);
      resizeObserver.disconnect();
    };
  }, [mapRef, popup]);

  const getLocationName = useLocationName();

  const availableSources = useMemo(
    () => Array.from(new Set(popup?.features?.map(({ source }) => source))),
    [popup]
  );

  const { data: layersInteractiveData } = useGetLayers(
    {
      locale,
      filters: {
        slug: {
          $in: layersInteractive,
        },
      },
    },
    {
      query: {
        enabled: layersInteractive.length > 1,
        select: ({ data }) => {
          const options = data
            .filter(
              ({
                config: {
                  // @ts-expect-error will check later
                  source: { id: sourceId },
                },
              }) => availableSources?.includes(sourceId)
            )
            .map(({ title, slug, interaction_config }) => ({
              label: title,
              value: slug,
              isProtectedArea:
                (interaction_config as InteractionConfig)?.['@@type'] === 'ProtectedAreaPopup',
            }))
            .sort((a, b) =>
              syncedLayers.indexOf(a.value) > syncedLayers.indexOf(b.value) ? 1 : -1
            );

          // Every protected-area layer renders the same popup, so they share one entry.
          const firstProtectedArea = options.find((option) => option.isProtectedArea);
          return options
            .filter((option) => !option.isProtectedArea || option === firstProtectedArea)
            .map(({ label, value, isProtectedArea }) => ({
              label: isProtectedArea ? t('protected-areas') : label,
              value,
            }));
        },
      },
    }
  );

  const hoverTooltipContent = useMemo(() => {
    const features = popup?.features ?? [];
    const isBoundary = (feature: (typeof features)[number]) =>
      feature.source in POPUP_PROPERTIES_BY_SOURCE;

    // Protected-area tiles are the ones carrying a WDPA or MPAtlas id; other
    // interactive layers (e.g. ProtectedSeas) must not be counted.
    const protectedAreaKey = (feature: (typeof features)[number]) => {
      const { WDPA_PID, wdpa_pid, zone_id, WDPAID, wdpa_id } = feature.properties ?? {};
      const id = WDPA_PID ?? wdpa_pid ?? zone_id ?? WDPAID ?? wdpa_id;
      return id == null ? null : `${feature.source}:${id}`;
    };

    // The boundary names the tooltip; protected areas under it are counted per
    // parcel, matching the click popup's cards. Mapbox returns one entry per style
    // layer and tile hit, so count distinct keys.
    const boundary = features.find(isBoundary);
    const protectedAreaCount = new Set(features.map(protectedAreaKey).filter(Boolean)).size;

    const { properties, source } = boundary ?? features[0] ?? {};

    const ids = new Set(['ISO_TER1', 'ISO_TER2', 'ISO_TER3']);
    const propertiesSet = properties ? new Set(Object.keys(properties)) : new Set();
    const isMultiClaimEEZ = source === EEZ_SOURCE && ids.intersection(propertiesSet).size >= 2;

    if (!properties) {
      return null;
    }

    // EEZ joint zones carry pre-localized names baked into the tile properties,
    // so keep the locale-keyed lookup for that source. Countries and
    // terrestrial/marine regions share the app-wide `useLocationName` resolver.
    let displayName: string | null = null;
    if (source === EEZ_SOURCE) {
      displayName = properties[POPUP_PROPERTIES_BY_SOURCE[source]?.name[locale]] ?? null;
    } else {
      const sourceConfig = POPUP_PROPERTIES_BY_SOURCE[source];
      const codeKey = sourceConfig?.ids?.find((k: string) => !!properties[k]);
      const code = codeKey ? properties[codeKey] : null;

      displayName =
        code && sourceConfig?.locationType
          ? getLocationName({ code, type: sourceConfig.locationType })
          : // Protected-area and ProtectedSeas tiles carry the site name directly.
            (properties.name ?? properties.NAME ?? properties.SITE_NAME ?? null);
    }

    return (
      <div>
        {POPUP_ICON_BY_SOURCE[source] ? (
          <Icon icon={POPUP_ICON_BY_SOURCE[source]} className="mr-2 inline-block w-[14px]" />
        ) : null}
        {displayName}
        {boundary && protectedAreaCount > 0 && (
          <div className="mt-[0.25rem]">
            {/* The count sits in the icon column, aligned with the boundary line above. */}
            <span className="mr-2 inline-block min-w-[14px]">{protectedAreaCount}</span>
            {t('protected-areas-count', { count: protectedAreaCount })}
          </div>
        )}
        {isMultiClaimEEZ && (
          <div className="mt-[0.25rem] text-xs">{`* ${t('eez-multi-claim')}`}</div>
        )}
      </div>
    );
  }, [locale, popup, t, getLocationName]);

  const closePopup = useCallback(() => {
    setPopup({});
  }, [setPopup]);

  useEffect(() => {
    if (!layersInteractive.length) {
      closePopup();
    }
  }, [layersInteractive, closePopup]);

  useEffect(() => {
    if (layersInteractiveData?.[0]?.value) {
      setSelectedLayerSlug(layersInteractiveData[0].value);
    }
  }, [layersInteractiveData]);

  useKey('Escape', closePopup);

  const isHoveredTooltip = popup?.type === 'mousemove';
  const isClickedTooltip = popup?.type === 'click';

  if (!Object.keys(popup).length || !popup?.features?.length) {
    return null;
  }

  return (
    <Popup
      ref={popupRef}
      latitude={popup.lngLat.lat}
      longitude={popup.lngLat.lng}
      anchor={anchor}
      offset={10}
      closeOnClick={false}
      closeButton={false}
      maxWidth="230px"
      onClose={closePopup}
      className={cn({
        'min-w-[250px]': !isHoveredTooltip,
      })}
    >
      <div className="space-y-2 p-4">
        {!isHoveredTooltip && (
          <div className="flex justify-end">
            <button onClick={closePopup}>
              <Icon icon={CloseIcon} className="h-3 w-3 fill-black" />
            </button>
          </div>
        )}
        {isClickedTooltip && (layersInteractiveData?.length ?? 0) > 1 && (
          <Select
            onValueChange={(layer) => {
              setSelectedLayerSlug(layer);
            }}
            value={selectedLayerSlug ?? undefined}
          >
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {layersInteractiveData?.map(({ label, value }) => (
                <SelectItem key={value} value={value}>
                  {label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        )}
        {isHoveredTooltip && (
          <div className="font-mono text-sm text-black">{hoverTooltipContent}</div>
        )}
        {isClickedTooltip && selectedLayerSlug && <PopupItem slug={selectedLayerSlug} />}
      </div>
    </Popup>
  );
};

PopupContainer.messages = [
  'containers.map',
  // Required by the `useLocationName` hook
  'locations',
  ...PopupItem.messages,
];

export default PopupContainer;
