import { useCallback, useEffect, useMemo, useState } from 'react';

import { Popup } from 'react-map-gl';

import { useAtomValue, useSetAtom } from 'jotai';
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
        select: ({ data }) =>
          data
            .filter(
              ({
                config: {
                  // @ts-expect-error will check later
                  source: { id: sourceId },
                },
              }) => availableSources?.includes(sourceId)
            )
            .map(({ title: label, slug: value }) => ({
              label,
              value,
            }))
            .sort((a, b) =>
              syncedLayers.indexOf(a.value) > syncedLayers.indexOf(b.value) ? 1 : -1
            ),
      },
    }
  );

  const hoverTooltipContent = useMemo(() => {
    const { properties, source } = popup?.features?.[0] ?? {};

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
      const codeKey = POPUP_PROPERTIES_BY_SOURCE[source]?.ids?.find((k: string) => !!properties[k]);
      const code = codeKey ? properties[codeKey] : null;
      const type = source === 'countries' ? 'country' : 'region';
      displayName = code ? getLocationName({ code, type }) : null;
    }

    return (
      <div>
        {POPUP_ICON_BY_SOURCE[source] ? (
          <Icon icon={POPUP_ICON_BY_SOURCE[source]} className="mr-2 inline-block w-[14px]" />
        ) : null}
        {displayName}
        <div className="mt-[0.25rem] text-xs">
          {isMultiClaimEEZ ? `* ${t('eez-multi-claim')}` : null}
        </div>
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
      latitude={popup.lngLat.lat}
      longitude={popup.lngLat.lng}
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
        {isClickedTooltip && availableSources.length > 1 && (
          <Select
            onValueChange={(layer) => {
              setSelectedLayerSlug(layer);
            }}
            defaultValue={layersInteractiveData?.[0].value}
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
