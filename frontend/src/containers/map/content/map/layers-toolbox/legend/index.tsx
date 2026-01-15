import { useCallback, useMemo } from 'react';

import { useAtom } from 'jotai';
import { useLocale, useTranslations } from 'next-intl';

import {
  useSyncMapLayerSettings,
  useSyncMapLayers,
} from '@/containers/map/content/map/sync-settings';
import { allActiveLayersAtom, customLayersAtom } from '@/containers/map/store';
import { cn } from '@/lib/classnames';
import { FCWithMessages } from '@/types';
import { useGetLayers } from '@/types/generated/layer';
import { LayerListResponseDataItem } from '@/types/generated/strapi.schemas';
import { LayerTyped, ParamsConfig } from '@/types/layers';

import LegendItem from './item';
import LegendItemHeader from './item-header';

const Legend: FCWithMessages = () => {
  const t = useTranslations('containers.map');
  const locale = useLocale();

  const [activeLayers, setPredefinedMapLayers] = useSyncMapLayers();
  const [layerSettings, setLayerSettings] = useSyncMapLayerSettings();

  const [customLayers, setCustomLayers] = useAtom(customLayersAtom);
  const [allActiveLayers, setAllActiveLayers] = useAtom(allActiveLayersAtom);

  const layersQuery = useGetLayers<LayerListResponseDataItem[]>(
    {
      locale,
      sort: 'title:asc',
      // @ts-ignore
      fields: ['title', 'params_config', 'slug'],

      // @ts-ignore
      populate: {
        legend_config: {
          populate: {
            items: true,
          },
        },
        environment: {
          fields: ['slug'],
        },
      },
    },
    {
      query: {
        select: ({ data }) =>
          data
            .filter(({ attributes: { slug } }) => activeLayers.includes(slug))
            .sort((a, b) => {
              const indexA = activeLayers.indexOf(a.attributes.slug);
              const indexB = activeLayers.indexOf(b.attributes.slug);
              return indexA - indexB;
            }),
        placeholderData: { data: [] },
        queryKey: ['layers', locale, activeLayers],
        keepPreviousData: true,
      },
    }
  );

  const onRemoveLayer = useCallback(
    (layerSlug: string) => {
      if (!customLayers[layerSlug]) {
        setPredefinedMapLayers((currentLayers) => {
          return currentLayers.filter((slug) => slug !== layerSlug);
        });
      } else {
        const updatedCustomLayers = { ...customLayers };
        updatedCustomLayers[layerSlug].isActive = false;
        setCustomLayers(updatedCustomLayers);
      }
      setAllActiveLayers((currentLayers) => {
        return currentLayers.filter((slug) => slug !== layerSlug);
      });
    },
    [customLayers, setAllActiveLayers, setCustomLayers, setPredefinedMapLayers]
  );

  const onToggleLayerVisibility = useCallback(
    (layerSlug: string, isVisible: boolean) => {
      if (!customLayers[layerSlug]) {
        setLayerSettings((prev) => ({
          ...prev,
          [layerSlug]: {
            ...prev[layerSlug],
            visibility: isVisible,
          },
        }));
      } else {
        const updatedCustomLayers = { ...customLayers };
        updatedCustomLayers[layerSlug].isVisible = !updatedCustomLayers[layerSlug].isVisible;
        setCustomLayers(updatedCustomLayers);
      }
    },
    [customLayers, setCustomLayers, setLayerSettings]
  );

  const onChangeLayerOpacity = useCallback(
    (layerSlug: string, opacity: number) => {
      setLayerSettings((prev) => ({
        ...prev,
        [layerSlug]: {
          ...prev[layerSlug],
          opacity,
        },
      }));
    },
    [setLayerSettings]
  );

  const moveLayer = useCallback(
    (layerSlug: string, direction: 'up' | 'down') => {
      const layerIndex = allActiveLayers.findIndex((slug) => slug === layerSlug);
      if (layerIndex === -1) {
        return;
      }
      const delta = direction === 'up' ? -1 : 1;

      if (!customLayers[layerSlug]) {
        const predfinedLayerIndex = activeLayers.findIndex((slug) => slug === layerSlug);
        setPredefinedMapLayers((prev) => {
          return prev
            .toSpliced(predfinedLayerIndex, 1)
            .toSpliced(predfinedLayerIndex + delta, 0, layerSlug);
        });
      }

      setAllActiveLayers((prev) =>
        prev.toSpliced(layerIndex, 1).toSpliced(layerIndex + delta, 0, layerSlug)
      );
    },
    [allActiveLayers, activeLayers, customLayers, setAllActiveLayers, setPredefinedMapLayers]
  );

  const onMoveLayerDown = useCallback(
    (layerSlug: string) => {
      moveLayer(layerSlug, 'down');
    },
    [moveLayer]
  );

  const onMoveLayerUp = useCallback(
    (layerSlug: string) => {
      moveLayer(layerSlug, 'up');
    },
    [moveLayer]
  );

  const legendItems = useMemo(() => {
    if (!layersQuery.data?.length) {
      return null;
    }

    return (
      <div>
        {allActiveLayers.map((slug, index) => {
          const isFirst = index === 0;
          const isLast = index + 1 === allActiveLayers.length;

          let opacity = 1;
          let isVisible = true;
          let title;
          let legend_config;
          let params_config;
          if (!customLayers[slug] && layersQuery.data?.length) {
            const layer = layersQuery.data.filter((layer) => layer.attributes.slug === slug)[0];

            // Short circuit to catch when allActiveLayers state updates and the layersQuery
            // hasn't yet returned the corresponding data
            if (!layer) return null;

            legend_config = layer.attributes.legend_config;
            params_config = layer.attributes.params_config;

            title = layer.attributes.title;
            isVisible = layerSettings[slug]?.visibility !== false;
            opacity = layerSettings[slug]?.opacity ?? 1;
          } else {
            title = customLayers[slug].name;
            isVisible = customLayers[slug].isVisible;
            legend_config = {
              id: +slug,
              type: 'icon',
              items: [
                {
                  color: '#000000',
                  description: null,
                  icon: 'circle-with-fill',
                  value: title,
                },
              ],
            };

            params_config = [
              {
                key: 'opacity',
                default: 1,
              },
            ];
          }

          return (
            <div
              key={slug}
              className={cn({
                'pb-3': index + 1 < allActiveLayers.length,
                'pt-2': index > 0,
              })}
            >
              <LegendItemHeader
                title={title}
                isFirst={isFirst}
                isLast={isLast}
                onMoveLayerDown={onMoveLayerDown}
                onMoveLayerUp={onMoveLayerUp}
                slug={slug}
                isVisible={isVisible}
                onChangeLayerOpacity={onChangeLayerOpacity}
                onRemoveLayer={onRemoveLayer}
                onToggleLayerVisibility={onToggleLayerVisibility}
                opacity={opacity}
              />
              <div className="pt-1.5">
                <LegendItem
                  config={legend_config as LayerTyped['legend_config']}
                  paramsConfig={params_config as ParamsConfig}
                />
              </div>
            </div>
          );
        })}
      </div>
    );
  }, [
    allActiveLayers,
    customLayers,
    layerSettings,
    layersQuery.data,
    onChangeLayerOpacity,
    onMoveLayerDown,
    onMoveLayerUp,
    onRemoveLayer,
    onToggleLayerVisibility,
  ]);

  return (
    <div className="px-4 py-2">
      {!layersQuery.data?.length && (
        <p>
          {t.rich('open-layers-to-add-to-map', {
            b: (chunks) => <span className="text-sm font-black uppercase">{chunks}</span>,
          })}
        </p>
      )}
      {legendItems}
    </div>
  );
};

Legend.messages = ['containers.map', ...LegendItem.messages, ...LegendItemHeader.messages];

export default Legend;
