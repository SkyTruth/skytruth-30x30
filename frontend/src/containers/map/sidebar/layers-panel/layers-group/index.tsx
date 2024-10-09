import { PropsWithChildren, useCallback, useEffect, useMemo, useState } from 'react';

import { useTranslations } from 'next-intl';
import { LuChevronDown, LuChevronUp } from 'react-icons/lu';

import TooltipButton from '@/components/tooltip-button';
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible';
import { Label } from '@/components/ui/label';
import { Switch } from '@/components/ui/switch';
import {
  useSyncMapLayers,
  useSyncMapLayerSettings,
} from '@/containers/map/content/map/sync-settings';
import { useSyncMapContentSettings } from '@/containers/map/sync-settings';
import { cn } from '@/lib/classnames';
import { FCWithMessages } from '@/types';
import { DatasetUpdatedByData, LayerResponseDataObject } from '@/types/generated/strapi.schemas';

export const SWITCH_LABEL_CLASSES = '-mb-px cursor-pointer pt-px font-mono text-xs font-normal';
const COLLAPSIBLE_TRIGGER_ICONS_CLASSES = 'w-5 h-5 hidden';
const COLLAPSIBLE_TRIGGER_CLASSES =
  'group flex w-full items-center justify-between py-2 text-xs font-bold';
const COLLAPSIBLE_CONTENT_CLASSES =
  'data-[state=closed]:animate-collapsible-up data-[state=open]:animate-collapsible-down border-black py-2';

type LayersGroupProps = PropsWithChildren<{
  name: string;
  datasets: DatasetUpdatedByData[];
  showDatasetsNames?: boolean;
  showBottomBorder?: boolean;
  isOpen?: boolean;
  loading?: boolean;
}>;

const LayersGroup: FCWithMessages<LayersGroupProps> = ({
  name,
  datasets,
  showDatasetsNames = true,
  showBottomBorder = true,
  isOpen = true,
  loading = true,
  children,
}): JSX.Element => {
  const [open, setOpen] = useState(isOpen);
  const t = useTranslations('containers.map-sidebar-layers-panel');

  const [activeLayers, setMapLayers] = useSyncMapLayers();
  const [layerSettings, setLayerSettings] = useSyncMapLayerSettings();
  const [{ tab }] = useSyncMapContentSettings();

  const datasetsLayersIds = useMemo(() => {
    return (
      datasets?.map(({ attributes }) => attributes?.layers?.data?.map(({ id }) => id))?.flat() || []
    );
  }, [datasets]);

  const numActiveDatasetsLayers = useMemo(() => {
    return datasetsLayersIds?.filter((id) => activeLayers?.includes(id))?.length || 0;
  }, [datasetsLayersIds, activeLayers]);

  const onToggleLayer = useCallback(
    (layerId: LayerResponseDataObject['id'], isActive: boolean) => {
      setMapLayers(
        isActive
          ? [...activeLayers, Number(layerId)]
          : activeLayers.filter((_layerId) => _layerId !== Number(layerId))
      );

      // If we don't have layerSettings entries, the view is in its default state; we wish to
      // show all legend accordion items expanded by default.
      const initialSettings = (() => {
        const layerSettingsKeys = Object.keys(layerSettings);
        if (layerSettingsKeys.length) return {};
        return Object.assign(
          {},
          ...activeLayers.map((layerId) => ({ [layerId]: { expanded: true } }))
        );
      })();

      setLayerSettings((prev) => ({
        ...initialSettings,
        ...prev,
        [layerId]: {
          ...prev[layerId],
          expanded: true,
        },
      }));
    },
    [activeLayers, layerSettings, setLayerSettings, setMapLayers]
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
                  {dataset.attributes?.layers?.data?.map((layer) => {
                    const isActive =
                      activeLayers.findIndex((layerId) => layerId === layer.id) !== -1;
                    const onCheckedChange = onToggleLayer.bind(null, layer.id) as (
                      isActive: boolean
                    ) => void;
                    const metadata = layer?.attributes?.metadata;

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
                          <TooltipButton className="mt-px" text={metadata?.description} />
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
