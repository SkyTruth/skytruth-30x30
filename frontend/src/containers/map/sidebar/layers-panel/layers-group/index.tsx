import { PropsWithChildren, useCallback, useEffect, useMemo, useState } from 'react';

import { useAtom } from 'jotai';
import { useTranslations } from 'next-intl';
import { LuChevronDown, LuChevronUp } from 'react-icons/lu';

import TooltipButton from '@/components/tooltip-button';
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible';
import { Label } from '@/components/ui/label';
import { Switch } from '@/components/ui/switch';
import { useSyncMapLayers } from '@/containers/map/content/map/sync-settings';
import { allActiveLayersAtom } from '@/containers/map/store';
import { useSyncMapContentSettings } from '@/containers/map/sync-settings';
import { cn } from '@/lib/classnames';
import { FCWithMessages } from '@/types';
import {
  DatasetUpdatedByData,
  Layer,
  LayerResponseDataObject,
} from '@/types/generated/strapi.schemas';

import {
  COLLAPSIBLE_TRIGGER_ICONS_CLASSES,
  COLLAPSIBLE_TRIGGER_CLASSES,
  COLLAPSIBLE_CONTENT_CLASSES,
  SWITCH_LABEL_CLASSES,
} from '../constants';

type LayersGroupProps = PropsWithChildren<{
  name: string;
  datasets: DatasetUpdatedByData[];
  showDatasetsNames?: boolean;
  showBottomBorder?: boolean;
  isOpen?: boolean;
  loading?: boolean;
  // Number of extra active layers for this group
  extraActiveLayers?: number;
}>;

const LayersGroup: FCWithMessages<LayersGroupProps> = ({
  name,
  datasets,
  showDatasetsNames = true,
  showBottomBorder = true,
  isOpen = true,
  loading = true,
  extraActiveLayers = 0,
  children,
}): JSX.Element => {
  const [open, setOpen] = useState(isOpen);
  const t = useTranslations('containers.map-sidebar-layers-panel');

  const [activeLayers, setMapLayers] = useSyncMapLayers();
  const [allActiveLayers, setAllActiveLayers] = useAtom(allActiveLayersAtom);
  const [{ tab }] = useSyncMapContentSettings();

  const datasetsLayerSlugs = useMemo(() => {
    return (
      datasets
        ?.map(({ attributes }) => attributes?.layers?.data?.map(({ slug }) => slug))
        ?.flat() || []
    );
  }, [datasets]);

  const numActiveDatasetsLayers = useMemo(() => {
    return (
      (datasetsLayerSlugs?.filter((slug) => activeLayers?.includes(slug))?.length ?? 0) +
      extraActiveLayers
    );
  }, [datasetsLayerSlugs, activeLayers, extraActiveLayers]);

  const onToggleLayer = useCallback(
    (layerSlug: Layer['slug'], isActive: boolean) => {
      setMapLayers(
        isActive
          ? [layerSlug, ...activeLayers]
          : activeLayers.filter((activeSlug) => activeSlug !== layerSlug)
      );
      setAllActiveLayers(
        isActive
          ? [layerSlug, ...allActiveLayers]
          : allActiveLayers.filter((activeSlug) => activeSlug !== layerSlug)
      );
    },
    [activeLayers, allActiveLayers, setAllActiveLayers, setMapLayers]
  );

  useEffect(() => {
    setOpen(isOpen);
  }, [isOpen, tab]);

  const displayNumActiveLayers = !open && numActiveDatasetsLayers > 0;
  const noData = !loading && !datasets?.length;

  return (
    <Collapsible open={open} onOpenChange={setOpen}>
      <CollapsibleTrigger
        className={cn(COLLAPSIBLE_TRIGGER_CLASSES, { 'border-b border-black': !open })}
      >
        <span>
          {name}
          {displayNumActiveLayers && (
            <span className="ml-2 border border-black px-1 font-normal">
              {numActiveDatasetsLayers}
            </span>
          )}
        </span>
        <LuChevronDown
          className={`group-data-[state=closed]:block ${COLLAPSIBLE_TRIGGER_ICONS_CLASSES}`}
        />
        <LuChevronUp
          className={`group-data-[state=open]:block ${COLLAPSIBLE_TRIGGER_ICONS_CLASSES}`}
        />
      </CollapsibleTrigger>
      <CollapsibleContent
        className={cn(COLLAPSIBLE_CONTENT_CLASSES, { 'border-b': showBottomBorder })}
      >
        <div className="space-y-4 divide-y divide-dashed divide-black">
          {loading && <span className="font-mono text-xs">{t('loading')}</span>}
          {noData && <span className="font-mono text-xs">{t('no-data-available')}</span>}
          {datasets?.map((dataset) => {
            return (
              <div key={dataset.id} className="[&:not(:first-child)]:pt-3">
                {showDatasetsNames && <h4 className="font-mono">{dataset?.attributes?.name}</h4>}
                <ul className={cn('my-3 flex flex-col space-y-3', { '-my-0': !showDatasetsNames })}>
                  {dataset.attributes?.layers?.data?.map((layer: LayerResponseDataObject) => {
                    const isActive = activeLayers?.includes(layer?.attributes?.slug);
                    const onCheckedChange = onToggleLayer.bind(null, layer?.attributes?.slug) as (
                      isActive: boolean
                    ) => void;
                    const metadata = layer?.attributes?.metadata;
                    const sources = metadata?.citation
                      ? [{ id: layer?.id, title: metadata?.citation, url: metadata?.source }]
                      : null;

                    return (
                      <li key={layer.id} className="flex items-start justify-between">
                        <span className="flex items-start gap-2">
                          <Switch
                            id={`${layer.id}-switch`}
                            className="mt-px"
                            checked={isActive}
                            onCheckedChange={onCheckedChange}
                          />
                          <Label htmlFor={`${layer.id}-switch`} className={SWITCH_LABEL_CLASSES}>
                            {layer.attributes.title}
                          </Label>
                        </span>
                        {metadata?.description && (
                          <TooltipButton
                            className="mt-px"
                            text={metadata?.description}
                            sources={sources}
                          />
                        )}
                      </li>
                    );
                  })}
                  <>{children}</>
                </ul>
              </div>
            );
          })}
        </div>
      </CollapsibleContent>
    </Collapsible>
  );
};

LayersGroup.messages = ['containers.map-sidebar-layers-panel', ...TooltipButton.messages];

export default LayersGroup;
