import { useCallback, useMemo, useState } from 'react';

import type { GeoJSONObject } from '@turf/turf';
import { useAtom, useSetAtom } from 'jotai';
import { useTranslations } from 'next-intl';
import { LuChevronDown, LuChevronUp } from 'react-icons/lu';

import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible';
import {
  allActiveLayersAtom,
  bboxLocationAtom,
  customLayersAtom,
  drawStateAtom,
  modellingCustomLayerIdAtom,
  sidebarAtom,
  modellingAtom,
} from '@/containers/map/store';
import useCustomLayersIndexedDB from '@/hooks/use-custom-layers-indexed-db';
import { cn } from '@/lib/classnames';
import { extractPolygons } from '@/lib/utils/file-upload';
import { getGeoJSONBoundingBox } from '@/lib/utils/geo';
import { FCWithMessages } from '@/types';
import { CustomLayer } from '@/types/layers';

import {
  COLLAPSIBLE_CONTENT_CLASSES,
  COLLAPSIBLE_TRIGGER_CLASSES,
  COLLAPSIBLE_TRIGGER_ICONS_CLASSES,
  MAX_CUSTOM_LAYERS,
  SWITCH_LABEL_CLASSES,
} from '../constants';
import UploadLayer from '../upload-layer';

import CustomLayerItem from './custom-layer-item';

type CustomLayerGroupProps = {
  name: string;
  showBottomBorder?: boolean;
  isOpen?: boolean;
};

const CustomLayerGroup: FCWithMessages<CustomLayerGroupProps> = ({
  name,
  showBottomBorder = true,
  isOpen = true,
}): JSX.Element => {
  const t = useTranslations('containers.map-sidebar-layers-panel');
  const tUploads = useTranslations('services.uploads');

  const [open, setOpen] = useState(isOpen);
  const [savingLayerIds, setSavingLayerIds] = useState<Record<CustomLayer['id'], boolean>>({});
  const [persistActionError, setPersistActionError] = useState<string | null>(null);

  const [customLayers, setCustomLayers] = useAtom(customLayersAtom);
  const [allActiveLayers] = useAtom(allActiveLayersAtom);
  const [modellingCustomLayerId, setModellingCustomLayerId] = useAtom(modellingCustomLayerIdAtom);
  const setDrawState = useSetAtom(drawStateAtom);
  const setModellingState = useSetAtom(modellingAtom);
  const setSidebarOpen = useSetAtom(sidebarAtom);
  const setBboxLocation = useSetAtom(bboxLocationAtom);
  const { savedLayers, isIndexedDBAvailable, saveLayer, deleteLayer } = useCustomLayersIndexedDB();

  const numCustomLayers = useMemo(() => Object.keys(customLayers).length, [customLayers]);

  const onToggleLayer = useCallback(
    (toggled: CustomLayer, checked: boolean) => {
      const updatedLayers = { ...customLayers };
      let updatedActiveLayers = [...allActiveLayers];
      updatedLayers[toggled.id].isActive = checked;

      if (checked) {
        updatedActiveLayers.unshift(toggled.id);
      } else {
        updatedActiveLayers = updatedActiveLayers.filter((id) => id !== toggled.id);
      }

      setCustomLayers(updatedLayers);
    },
    [allActiveLayers, customLayers, setCustomLayers]
  );

  const onDeleteLayer = useCallback(
    async (slug: string) => {
      const updatedLayers = { ...customLayers };
      delete updatedLayers[slug];

      setPersistActionError(null);
      setCustomLayers(updatedLayers);
      setSavingLayerIds((prev) => {
        const next = { ...prev };
        delete next[slug];
        return next;
      });
      if (modellingCustomLayerId === slug) {
        setModellingCustomLayerId(null);
      }

      try {
        await deleteLayer(slug);
      } catch {
        setPersistActionError(t('delete-layer-error'));
      }
    },
    [
      customLayers,
      deleteLayer,
      modellingCustomLayerId,
      setCustomLayers,
      setModellingCustomLayerId,
      t,
    ]
  );

  const onCommitEdit = useCallback(
    (slug: string, newName: string) => {
      setCustomLayers((prev) => {
        if (!prev[slug]) return prev;
        return {
          ...prev,
          [slug]: {
            ...prev[slug],
            name: newName,
          },
        };
      });
    },
    [setCustomLayers]
  );

  const onUseLayerForModelling = useCallback(
    (layer: CustomLayer) => {
      setSidebarOpen(true);

      try {
        const { feature } = extractPolygons(layer.feature as GeoJSONObject);

        setDrawState((prevState) => ({
          ...prevState,
          active: false,
          status: 'success',
          feature,
          revision: prevState.revision + 1,
          source: 'upload',
        }));
        setModellingState((prevState) => ({ ...prevState, active: true }));
        setModellingCustomLayerId(layer.id);

        const bounds = getGeoJSONBoundingBox(feature);
        if (bounds) {
          setBboxLocation(bounds as [number, number, number, number]);
        }
      } catch {
        setModellingState((prevState) => ({
          ...prevState,
          status: 'error',
          errorMessage: tUploads('no-polygons-error'),
        }));
      }
    },
    [
      setBboxLocation,
      setDrawState,
      setModellingCustomLayerId,
      setModellingState,
      setSidebarOpen,
      tUploads,
    ]
  );

  const onSaveLayer = useCallback(
    async (layer: CustomLayer) => {
      if (!isIndexedDBAvailable) return;

      setPersistActionError(null);
      setSavingLayerIds((prev) => ({
        ...prev,
        [layer.id]: true,
      }));

      try {
        await saveLayer(layer);
      } catch {
        setPersistActionError(t('save-layer-error'));
      } finally {
        setSavingLayerIds((prev) => {
          const next = { ...prev };
          delete next[layer.id];
          return next;
        });
      }
    },
    [isIndexedDBAvailable, saveLayer, t]
  );

  const savedLayerSnapshots = useMemo(
    () =>
      savedLayers.reduce(
        (acc, layer) => {
          acc[layer.id] = JSON.stringify(layer);
          return acc;
        },
        {} as Record<CustomLayer['id'], string>
      ),
    [savedLayers]
  );

  const isUploadDisabled = useMemo(
    () => Object.keys(customLayers).length >= MAX_CUSTOM_LAYERS,
    [customLayers]
  );

  const displayNumLayers = numCustomLayers > 0;

  return (
    <Collapsible open={open} onOpenChange={setOpen}>
      <CollapsibleTrigger
        className={cn(COLLAPSIBLE_TRIGGER_CLASSES, { 'border-b border-black': !open })}
      >
        <span>
          {name}
          {displayNumLayers && (
            <span className="ml-2 border border-black px-1 font-normal">{numCustomLayers}</span>
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
        className={cn(COLLAPSIBLE_CONTENT_CLASSES, {
          'border-b': showBottomBorder,
          'py-0': true,
        })}
      >
        <div>
          <UploadLayer isDisabled={isUploadDisabled} />
          {persistActionError && (
            <p className="px-2 pt-2 text-xs text-error" role="alert">
              {persistActionError}
            </p>
          )}
          <div className="pt3">
            <ul className={'my-3 flex flex-col space-y-3'}>
              {Object.keys(customLayers).map((slug) => {
                const layer = customLayers[slug];
                const isActive = layer.isActive;
                const layerSnapshot = JSON.stringify(layer);
                const isLayerSaved = savedLayerSnapshots[slug] === layerSnapshot;
                const isLayerSaving = Boolean(savingLayerIds[slug]);
                const isSaveUnavailable = !isIndexedDBAvailable;
                const isSaveDisabled = isLayerSaved || isLayerSaving || isSaveUnavailable;
                const saveLayerLabel = isLayerSaved ? t('layer-saved') : t('save-layer');
                const saveTooltipLabel = isSaveUnavailable
                  ? t('save-layer-unavailable')
                  : saveLayerLabel;

                return (
                  <CustomLayerItem
                    key={slug}
                    slug={slug}
                    layer={layer}
                    isActive={isActive}
                    switchLabelClassName={SWITCH_LABEL_CLASSES}
                    saveTooltipLabel={saveTooltipLabel}
                    isSaveDisabled={isSaveDisabled}
                    isUseForModellingDisabled={modellingCustomLayerId === slug}
                    onToggleLayer={onToggleLayer}
                    onCommitEdit={onCommitEdit}
                    onSaveLayer={onSaveLayer}
                    onUseLayerForModelling={onUseLayerForModelling}
                    onDeleteLayer={onDeleteLayer}
                  />
                );
              })}
            </ul>
          </div>
        </div>
      </CollapsibleContent>
    </Collapsible>
  );
};

CustomLayerGroup.messages = [
  'containers.map-sidebar-layers-panel',
  'services.uploads',
  ...UploadLayer.messages,
  ...CustomLayerItem.messages,
];

export default CustomLayerGroup;
