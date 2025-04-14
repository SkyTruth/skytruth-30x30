import { useCallback, useMemo } from 'react';

import { useLocale, useTranslations } from 'next-intl';
import { HiEye, HiEyeOff } from 'react-icons/hi';

import { Button } from '@/components/ui/button';
import Icon from '@/components/ui/icon';
import { Label } from '@/components/ui/label';
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover';
import { Slider } from '@/components/ui/slider';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip';
import {
  useSyncMapLayerSettings,
  useSyncMapLayers,
} from '@/containers/map/content/map/sync-settings';
import { useSyncMapContentSettings } from '@/containers/map/sync-settings';
import { cn } from '@/lib/classnames';
import ArrowDownIcon from '@/styles/icons/arrow-down.svg';
import ArrowTopIcon from '@/styles/icons/arrow-top.svg';
import CloseIcon from '@/styles/icons/close.svg';
import OpacityIcon from '@/styles/icons/opacity.svg';
import { FCWithMessages } from '@/types';
import { useGetLayers } from '@/types/generated/layer';
import {
  LayerListResponseDataItem,
  LayerResponseDataObject,
} from '@/types/generated/strapi.schemas';
import { LayerTyped, ParamsConfig } from '@/types/layers';

import LegendItem from './item';

const Legend: FCWithMessages = () => {
  const t = useTranslations('containers.map');
  const locale = useLocale();

  const [activeLayers, setMapLayers] = useSyncMapLayers();
  const [layerSettings, setLayerSettings] = useSyncMapLayerSettings();
  const [{ tab }] = useSyncMapContentSettings();

  const layersQuery = useGetLayers<LayerListResponseDataItem[]>(
    {
      locale,
      sort: 'title:asc',
      // eslint-disable-next-line @typescript-eslint/ban-ts-comment
      // @ts-ignore
      fields: ['title', 'params_config', 'slug'],
      // eslint-disable-next-line @typescript-eslint/ban-ts-comment
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
      filters: {
        ...(tab !== 'summary'
          ? {
            environment: {
              slug: {
                $in: tab,
              },
            },
          }
          : {}),
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
        queryKey: ['layers', activeLayers],
        keepPreviousData: true,
      },
    }
  );

  const onRemoveLayer = useCallback(
    (layerSlug: LayerResponseDataObject['attributes']['slug']) =>
      setMapLayers((currentLayers) => {
        return currentLayers.filter((slug) => slug !== layerSlug);
      }),
    [setMapLayers]
  );

  const onToggleLayerVisibility = useCallback(
    (layerSlug: LayerResponseDataObject['attributes']['slug'], isVisible: boolean) => {
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
    (layerSlug: LayerResponseDataObject['attributes']['slug'], opacity: number) => {
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
    (layerSlug: LayerResponseDataObject['attributes']['slug']) => {
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
    (layerSlug: LayerResponseDataObject['attributes']['slug']) => {
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
        {layersQuery.data?.map(
          ({ attributes: { title, legend_config, params_config, slug } }, index) => {
            const isFirst = index === 0;
            const isLast = index + 1 === layersQuery.data.length;

            const isVisible = layerSettings[slug]?.visibility !== false;
            const opacity = layerSettings[slug]?.opacity ?? 1;

            return (
              <div
                key={slug}
                className={cn({
                  'pb-3': index + 1 < activeLayers.length,
                  'pt-2': index > 0,
                })}
              >
                <div className="flex items-center justify-between gap-4">
                  <TooltipProvider>
                    <Tooltip>
                      <TooltipTrigger asChild>
                        <div className="overflow-hidden text-ellipsis whitespace-nowrap font-mono text-xs font-bold ring-offset-white transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-black focus-visible:ring-offset-2 [&_svg]:aria-[expanded=true]:rotate-180">
                          {title}
                        </div>
                      </TooltipTrigger>
                      <TooltipContent>{title}</TooltipContent>
                    </Tooltip>
                  </TooltipProvider>
                  <TooltipProvider>
                    <div className="flex shrink-0 items-center">
                      <Tooltip delayDuration={0}>
                        <TooltipTrigger asChild>
                          <Button
                            type="button"
                            variant="ghost"
                            size="icon-sm"
                            disabled={isFirst}
                            onClick={() => onMoveLayerUp(slug)}
                          >
                            <span className="sr-only">{t('move-up')}</span>
                            <Icon icon={ArrowTopIcon} className="h-3 w-3" />
                          </Button>
                        </TooltipTrigger>
                        <TooltipContent>{t('move-up')}</TooltipContent>
                      </Tooltip>
                      <Tooltip>
                        <TooltipTrigger asChild>
                          <Button
                            type="button"
                            variant="ghost"
                            size="icon-sm"
                            disabled={isLast}
                            onClick={() => onMoveLayerDown(slug)}
                          >
                            <span className="sr-only">{t('move-down')}</span>
                            <Icon icon={ArrowDownIcon} className="h-3 w-3" />
                          </Button>
                        </TooltipTrigger>
                        <TooltipContent>{t('move-down')}</TooltipContent>
                      </Tooltip>
                      <Tooltip>
                        <Popover>
                          <TooltipTrigger asChild>
                            <PopoverTrigger asChild>
                              <Button type="button" variant="ghost" size="icon-sm">
                                <span className="sr-only">{t('change-opacity')}</span>
                                <Icon icon={OpacityIcon} className="h-3.5 w-3.5" />
                              </Button>
                            </PopoverTrigger>
                          </TooltipTrigger>
                          <TooltipContent>{t('change-opacity')}</TooltipContent>
                          <PopoverContent className="w-48">
                            <Label className="mb-2 block text-xs">{t('opacity')}</Label>
                            <Slider
                              thumbLabel={t('opacity')}
                              defaultValue={[opacity]}
                              max={1}
                              step={0.1}
                              onValueCommit={([value]) => onChangeLayerOpacity(slug, value)}
                            />
                          </PopoverContent>
                        </Popover>
                      </Tooltip>
                      <Tooltip>
                        <TooltipTrigger asChild>
                          <Button
                            type="button"
                            variant="ghost"
                            size="icon-sm"
                            onClick={() => onToggleLayerVisibility(slug, !isVisible)}
                          >
                            <span className="sr-only">{isVisible ? t('hide') : t('show')}</span>
                            {isVisible && <HiEye className="h-4 w-4" aria-hidden />}
                            {!isVisible && <HiEyeOff className="h-4 w-4" aria-hidden />}
                          </Button>
                        </TooltipTrigger>
                        <TooltipContent>{isVisible ? t('hide') : t('show')}</TooltipContent>
                      </Tooltip>
                      <Tooltip>
                        <TooltipTrigger asChild>
                          <Button
                            type="button"
                            variant="ghost"
                            size="icon-sm"
                            onClick={() => {
                              onRemoveLayer(slug);
                            }}
                          >
                            <span className="sr-only">{t('remove')}</span>
                            <Icon icon={CloseIcon} className="h-3 w-3" />
                          </Button>
                        </TooltipTrigger>
                        <TooltipContent>{t('remove')}</TooltipContent>
                      </Tooltip>
                    </div>
                  </TooltipProvider>
                </div>
                <div className="pt-1.5">
                  <LegendItem
                    config={legend_config as LayerTyped['legend_config']}
                    paramsConfig={params_config as ParamsConfig}
                  />
                </div>
              </div>
            );
          }
        )}
      </div>
    );
  }, [
    activeLayers.length,
    layerSettings,
    layersQuery.data,
    onChangeLayerOpacity,
    onMoveLayerDown,
    onMoveLayerUp,
    onRemoveLayer,
    onToggleLayerVisibility,
    t,
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

Legend.messages = ['containers.map', ...LegendItem.messages];

export default Legend;
