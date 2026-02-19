import { PropsWithChildren, useCallback, useEffect, useMemo, useRef, useState } from 'react';

import type { GeoJSONObject } from '@turf/turf';
import { useAtom, useSetAtom } from 'jotai';
import { BarChartHorizontal, Save, Trash } from 'lucide-react';
import { useTranslations } from 'next-intl';
import { LuChevronDown, LuChevronUp } from 'react-icons/lu';

import TooltipButton from '@/components/tooltip-button';
import { Button } from '@/components/ui/button';
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible';
import { Label } from '@/components/ui/label';
import { Switch } from '@/components/ui/switch';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip';
import {
  allActiveLayersAtom,
  bboxLocationAtom,
  customLayersAtom,
  drawStateAtom,
  modellingAtom,
} from '@/containers/map/store';
import useCustomLayersIndexedDB from '@/hooks/use-custom-layers-indexed-db';
import { cn } from '@/lib/classnames';
import { extractPolygons } from '@/lib/utils/file-upload';
import { getGeoJSONBoundingBox } from '@/lib/utils/geo';
import { FCWithMessages } from '@/types';
import { CustomLayer } from '@/types/layers';

import {
  COLLAPSIBLE_TRIGGER_ICONS_CLASSES,
  COLLAPSIBLE_TRIGGER_CLASSES,
  COLLAPSIBLE_CONTENT_CLASSES,
  SWITCH_LABEL_CLASSES,
  MAX_CUSTOM_LAYERS,
} from '../constants';
import UploadLayer from '../upload-layer';

type CustomLayersGroupProps = PropsWithChildren<{
  name: string;
  showBottomBorder?: boolean;
  isOpen?: boolean;
}>;

const CustomLayersGroup: FCWithMessages<CustomLayersGroupProps> = ({
  name,
  showBottomBorder = true,
  isOpen = true,
  children,
}): JSX.Element => {
  const t = useTranslations('containers.map-sidebar-layers-panel');
  const tUploads = useTranslations('services.uploads');

  const [open, setOpen] = useState(isOpen);
  const [editingSlug, setEditingSlug] = useState<string | null>(null);
  const [draftName, setDraftName] = useState<string>('');
  const [savingLayerIds, setSavingLayerIds] = useState<Record<CustomLayer['id'], boolean>>({});

  const inputRef = useRef<HTMLInputElement | null>(null);

  const [customLayers, setCustomLayers] = useAtom(customLayersAtom);
  const [allActiveLayers] = useAtom(allActiveLayersAtom);
  const setDrawState = useSetAtom(drawStateAtom);
  const setModellingState = useSetAtom(modellingAtom);
  const setBboxLocation = useSetAtom(bboxLocationAtom);
  const { savedLayers, hasLoadedSavedLayers, isIndexedDBAvailable, saveLayer, deleteLayer } =
    useCustomLayersIndexedDB();

  useEffect(() => {
    if (editingSlug) {
      requestAnimationFrame(() => inputRef.current?.focus());
    }
  }, [editingSlug]);

  useEffect(() => {
    if (!hasLoadedSavedLayers || savedLayers.length === 0) return;

    setCustomLayers((prev) => {
      const next = { ...prev };
      let hasChanges = false;

      savedLayers.forEach((layer) => {
        if (!next[layer.id]) {
          next[layer.id] = layer;
          hasChanges = true;
        }
      });

      return hasChanges ? next : prev;
    });
  }, [hasLoadedSavedLayers, savedLayers, setCustomLayers]);

  const numCustomLayers = useMemo(() => {
    return Object.keys(customLayers).length;
  }, [customLayers]);

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
    (slug: string) => {
      const updatedLayers = { ...customLayers };
      delete updatedLayers[slug];

      setCustomLayers(updatedLayers);
      setSavingLayerIds((prev) => {
        const next = { ...prev };
        delete next[slug];
        return next;
      });
      void deleteLayer(slug).catch(() => {
        // Delete failures should not block layer interactions.
      });
    },
    [customLayers, deleteLayer, setCustomLayers]
  );

  const onRenameLayer = useCallback(
    (slug: string, newName: string) => {
      setCustomLayers((prev) => {
        prev[slug].name = newName;
        return {
          ...prev,
        };
      });
    },
    [setCustomLayers]
  );

  const onUseLayerForModelling = useCallback(
    (layer: CustomLayer) => {
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

        const bounds = getGeoJSONBoundingBox(feature);
        if (bounds) {
          setBboxLocation(bounds as [number, number, number, number]);
        }
      } catch {
        // Invalid/non-polygon custom layers cannot be used for modelling.
        setModellingState((prevState) => ({
          ...prevState,
          status: 'error',
          errorMessage: tUploads('no-polygons-error'),
        }));
      }
    },
    [setBboxLocation, setDrawState, setModellingState, tUploads]
  );

  const onSaveLayer = useCallback(
    async (layer: CustomLayer) => {
      if (!isIndexedDBAvailable) return;

      setSavingLayerIds((prev) => ({
        ...prev,
        [layer.id]: true,
      }));

      try {
        await saveLayer(layer);
      } catch {
        // Save failures should not block layer interactions.
      } finally {
        setSavingLayerIds((prev) => {
          const next = { ...prev };
          delete next[layer.id];
          return next;
        });
      }
    },
    [isIndexedDBAvailable, saveLayer]
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

  const beginEdit = (slug: string, currentName: string) => {
    setEditingSlug(slug);
    setDraftName(currentName);
  };

  const cancelEdit = () => {
    setEditingSlug(null);
    setDraftName('');
  };

  const commitEdit = (slug: string) => {
    const next = draftName.trim();
    if (next.length === 0) return cancelEdit();

    if (customLayers[slug]?.name !== next) {
      onRenameLayer(slug, next);
    }
    cancelEdit();
  };

  const isUploadDisabled = useMemo(() => {
    return Object.keys(customLayers).length >= MAX_CUSTOM_LAYERS;
  }, [customLayers]);

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
          <div className="pt3">
            <ul className={'my-3 flex flex-col space-y-3'}>
              {Object.keys(customLayers).map((slug) => {
                const layer = customLayers[slug];
                const isActive = layer.isActive;
                const isEditing = editingSlug === slug;
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
                  <li key={slug} className="flex items-start justify-between">
                    <span className="flex items-start gap-2 overflow-x-hidden text-nowrap">
                      <Switch
                        id={`${layer.name}-switch`}
                        aria-label={layer.name}
                        className="mt-px"
                        checked={isActive}
                        onCheckedChange={() => onToggleLayer(layer, !isActive)}
                      />

                      <div className="max-w-full">
                        {isEditing ? (
                          <div className="flex items-center gap-2">
                            <input
                              ref={inputRef}
                              value={draftName}
                              onChange={(event) => setDraftName(event.target.value)}
                              onKeyDown={(event) => {
                                if (event.key === 'Enter') commitEdit(slug);
                                if (event.key === 'Escape') cancelEdit();
                              }}
                              onBlur={() => commitEdit(slug)}
                              aria-label={t('edit-layer-name', { layer: layer.name })}
                              className={cn(
                                'w-full rounded-md border border-black bg-white px-2 py-1 text-sm',
                                'focus:outline-none focus:ring-2 focus:ring-black/30'
                              )}
                            />
                          </div>
                        ) : (
                          <Label
                            htmlFor={`${layer.name}-switch`}
                            className={cn(SWITCH_LABEL_CLASSES)}
                          >
                            <button
                              type="button"
                              className="hover:bg-gray-200 hover:text-gray-700 focus-visible:ring-black"
                              onClick={() => beginEdit(slug, layer.name)}
                            >
                              <span className="sr-only">{t('edit-layer-name')}</span>
                              {layer.name}
                            </button>
                          </Label>
                        )}
                      </div>
                    </span>

                    <TooltipProvider>
                      <div className="flex items-center">
                        <Tooltip delayDuration={0}>
                          <TooltipTrigger asChild>
                            <span className="inline-flex">
                              <Button
                                className="h-auto w-auto pl-1.5"
                                type="button"
                                size="icon-sm"
                                variant="ghost"
                                disabled={isSaveDisabled}
                                onClick={() => void onSaveLayer(layer)}
                              >
                                <span className="sr-only">{saveTooltipLabel}</span>
                                <Save size={16} />
                              </Button>
                            </span>
                          </TooltipTrigger>
                          <TooltipContent>{saveTooltipLabel}</TooltipContent>
                        </Tooltip>
                        <Tooltip delayDuration={0}>
                          <TooltipTrigger asChild>
                            <Button
                              className="h-auto w-auto pl-1.5"
                              type="button"
                              size="icon-sm"
                              variant="ghost"
                              onClick={() => onUseLayerForModelling(layer)}
                            >
                              <span className="sr-only">{t('use-layer-for-modelling')}</span>
                              <BarChartHorizontal size={16} />
                            </Button>
                          </TooltipTrigger>
                          <TooltipContent>{t('use-layer-for-modelling')}</TooltipContent>
                        </Tooltip>
                        <Tooltip delayDuration={0}>
                          <TooltipTrigger asChild>
                            <Button
                              className="h-auto w-auto pl-1.5"
                              type="button"
                              size="icon-sm"
                              variant="ghost"
                              onClick={() => onDeleteLayer(slug)}
                            >
                              <span className="sr-only">{t('delete-layer')}</span>
                              <Trash size={16} />
                            </Button>
                          </TooltipTrigger>
                          <TooltipContent>{t('delete-layer')}</TooltipContent>
                        </Tooltip>
                      </div>
                    </TooltipProvider>
                  </li>
                );
              })}
              <>{children}</>
            </ul>
          </div>
        </div>
      </CollapsibleContent>
    </Collapsible>
  );
};

CustomLayersGroup.messages = [
  'containers.map-sidebar-layers-panel',
  'services.uploads',
  ...TooltipButton.messages,
  ...UploadLayer.messages,
];

export default CustomLayersGroup;
