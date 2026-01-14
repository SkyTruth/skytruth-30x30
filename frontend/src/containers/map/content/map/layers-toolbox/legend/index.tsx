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

  const [activeLayers, setMapLayers] = useSyncMapLayers();
  const [layerSettings, setLayerSettings] = useSyncMapLayerSettings();

  const [customLayers] = useAtom(customLayersAtom);
  const [allActiveLayers] = useAtom(allActiveLayersAtom);

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
    (layerSlug: string) =>
      setMapLayers((currentLayers) => {
        return currentLayers.filter((slug) => slug !== layerSlug);
      }),
    [setMapLayers]
  );

  const onToggleLayerVisibility = useCallback(
    (layerSlug: string, isVisible: boolean) => {
      setLayerSettings((prev) => ({
        ...prev,
        [layerSlug]: {
          ...prev[layerSlug],
          visibility: isVisible,
        },
      }));
    },
    [setLayerSettings]
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

  const onMoveLayerDown = useCallback(
    (layerSlug: string) => {
      const layerIndex = activeLayers.findIndex((slug) => slug === layerSlug);
      if (layerIndex === -1) {
        return;
      }

      setMapLayers((prev) => {
        return prev.toSpliced(layerIndex, 1).toSpliced(layerIndex + 1, 0, layerSlug);
      });
    },
    [activeLayers, setMapLayers]
  );

  const onMoveLayerUp = useCallback(
    (layerSlug: string) => {
      const layerIndex = activeLayers.findIndex((slug) => slug === layerSlug);
      if (layerIndex === -1) {
        return;
      }

      setMapLayers((prev) => {
        return prev.toSpliced(layerIndex, 1).toSpliced(layerIndex - 1, 0, layerSlug);
      });
    },
    [activeLayers, setMapLayers]
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
