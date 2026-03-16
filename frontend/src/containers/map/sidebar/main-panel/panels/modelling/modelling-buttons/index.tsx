import { ChangeEventHandler, useCallback, useRef, useState } from 'react';

import { useQueryClient } from '@tanstack/react-query';
import type { GeoJSONObject } from '@turf/turf';
import { useAtom, useSetAtom } from 'jotai';
import { Upload } from 'lucide-react';
import { useTranslations } from 'next-intl';
import { RxTransform } from 'react-icons/rx';

import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import {
  MAX_CUSTOM_LAYER_SIZE,
  MAX_CUSTOM_LAYERS,
} from '@/containers/map/sidebar/layers-panel/constants';
import {
  bboxLocationAtom,
  customLayersAtom,
  modellingAtom,
  modellingCustomLayerIdAtom,
  drawStateAtom,
} from '@/containers/map/store';
import { useSyncMapContentSettings } from '@/containers/map/sync-settings';
import { useFeatureFlag } from '@/hooks/use-feature-flag'; // TECH-3372: tear down
import { FileTooLargeError, useUploadErrorMessage } from '@/hooks/use-upload-error-message';
import { cn } from '@/lib/classnames';
import { createCustomLayer } from '@/lib/utils/create-custom-layer';
import {
  extractPolygons,
  convertFilesToGeojson,
  supportedFileformats,
} from '@/lib/utils/file-upload';
import { getGeoJSONBoundingBox } from '@/lib/utils/geo';
import { validateGeometryForModelling } from '@/lib/utils/validate-geometry-for-modelling';
import { FCWithMessages } from '@/types';

const COMMON_BUTTON_CLASSES =
  'flex h-10 justify-between border-t border-black px- md:px-8 w-full pt-1 font-mono text-xs normal-case justify-center';

type ModellingButtonsProps = {
  className?: HTMLDivElement['className'];
};

const ModellingButtons: FCWithMessages<ModellingButtonsProps> = ({ className }) => {
  const t = useTranslations('containers.map-sidebar-main-panel');
  const getUploadErrorMessage = useUploadErrorMessage({
    maxFileSize: MAX_CUSTOM_LAYER_SIZE,
  });

  // TECH-3372: tear down
  const isCustomLayersActive = useFeatureFlag('is_custom_layers_active');

  const queryClient = useQueryClient();
  const [{ tab }] = useSyncMapContentSettings();
  const [modellingState, setModelling] = useAtom(modellingAtom);
  const { status: modellingStatus } = modellingState;

  const [drawState, setDrawState] = useAtom(drawStateAtom);
  const { active, status } = drawState;

  const [customLayers, setCustomLayers] = useAtom(customLayersAtom);
  const setModellingCustomLayerId = useSetAtom(modellingCustomLayerIdAtom);
  const setBboxLocation = useSetAtom(bboxLocationAtom);

  const [uploadError, setUploadError] = useState<string | null>(null);

  const uploadInputRef = useRef<HTMLInputElement | null>(null);

  const onUploadChange: ChangeEventHandler<HTMLInputElement> = useCallback(
    (event) => {
      const input = event.currentTarget;
      const files = Array.from(input.files ?? []);
      const previousDrawState = drawState;
      void (async () => {
        if (files.length === 0) {
          return;
        }

        setUploadError(null);
        setDrawState((prevState) => ({
          ...prevState,
          active: false,
          status: 'uploading',
        }));

        let totalSize = 0;
        for (const file of files) {
          totalSize += file.size;
        }

        try {
          if (totalSize > MAX_CUSTOM_LAYER_SIZE) {
            throw new FileTooLargeError();
          }

          const geojson = await convertFilesToGeojson(files);

          // Check if the geometry contains polygons for modelling
          let canBeUsedForModelling = false;
          let geometryError = null;
          try {
            extractPolygons(geojson as GeoJSONObject);
            canBeUsedForModelling = true;
          } catch (error) {
            // Layer has no polygon geometry — still added to map, just not used for modelling
            geometryError = error;
          }

          // Add full geometry as custom layer (all geometry types render on map)
          const layer = createCustomLayer(
            files[0].name,
            geojson,
            customLayers,
            canBeUsedForModelling
          );

          setCustomLayers((prev) => ({
            ...prev,
            [layer.id]: layer,
          }));

          setDrawState((prevState) => ({
            ...prevState,
            active: false,
            status: 'success',
            source: 'upload',
          }));

          const bounds = getGeoJSONBoundingBox(geojson);
          if (bounds) {
            setBboxLocation([...bounds] as [number, number, number, number]);
          }

          // setUploadError(null);

          // Validate geometry server-side before activating modelling
          if (canBeUsedForModelling) {
            const polygonFeature = extractPolygons(geojson as GeoJSONObject).feature;
            const { valid } = await validateGeometryForModelling(
              queryClient,
              tab,
              layer.id,
              polygonFeature
            );

            if (!valid) {
              setCustomLayers((prev) => ({
                ...prev,
                [layer.id]: { ...prev[layer.id], canBeUsedForModelling: false },
              }));
              if (!modellingState.active) {
                setUploadError(t('invalid-geometry-for-stats'));
              }
            } else if (!modellingState.active) {
              setModellingCustomLayerId(layer.id);
              setModelling((prevState) => ({ ...prevState, active: true }));
            }
          } else {
            setUploadError(geometryError ? getUploadErrorMessage(geometryError) : null);
          }
        } catch (error) {
          setDrawState(previousDrawState);
          setUploadError(getUploadErrorMessage(error));
        } finally {
          // Reset input value so uploading the same file again triggers onChange
          input.value = '';
        }
      })();
    },
    [
      t,
      tab,
      drawState,
      customLayers,
      getUploadErrorMessage,
      modellingState.active,
      queryClient,
      setDrawState,
      setCustomLayers,
      setModellingCustomLayerId,
      setModelling,
      setBboxLocation,
    ]
  );

  const onOpenUploadPicker = useCallback(() => {
    setUploadError(null);
    uploadInputRef.current?.click();
  }, []);

  const isUploadProcessing = status === 'uploading';
  const isAtMaxLayers = Object.keys(customLayers).length >= MAX_CUSTOM_LAYERS;
  const isUploadDisabled =
    active ||
    status === 'drawing' ||
    status === 'uploading' ||
    modellingStatus === 'running' ||
    isAtMaxLayers;

  const isDrawing = active || status === 'drawing';
  const isDrawDisabled = isUploadProcessing || (!isDrawing && isAtMaxLayers);

  return (
    <div className={cn('flex w-full flex-col font-mono', className)}>
      {
        // TODO: TECH-3372 remove feature flag check
        isCustomLayersActive ? (
          <>
            <label htmlFor="upload-layer" className="sr-only">
              {t('upload-layer')}
            </label>
            <Input
              id="upload-layer"
              ref={uploadInputRef}
              type="file"
              multiple
              accept={supportedFileformats.map((ext) => `.${ext}`).join(',')}
              className="hidden"
              onChange={onUploadChange}
              disabled={isUploadDisabled}
              aria-describedby={uploadError ? 'modelling-button-error' : undefined}
              aria-invalid={Boolean(uploadError)}
            />
          </>
        ) : null
      }

      <div className="flex w-full flex-col space-y-2">
        <div className="flex w-full gap-3 px-5">
          <Button
            className={COMMON_BUTTON_CLASSES}
            size="full"
            disabled={isDrawDisabled}
            onClick={() => {
              setUploadError(null);
              if (isDrawing) {
                setDrawState({ active: false, status: 'idle', source: null });
              } else {
                setDrawState((prevState) => ({ ...prevState, active: true }));
              }
            }}
          >
            <RxTransform className="mr-3 h-4 w-4" aria-hidden />
            {isDrawing ? t('cancel-drawing') : t('draw-shape')}
          </Button>
          {
            // TODO: TECH-3372 remove feature flag check
            isCustomLayersActive ? (
              <Button
                className={COMMON_BUTTON_CLASSES}
                size="full"
                type="button"
                onClick={onOpenUploadPicker}
                disabled={isUploadDisabled}
                aria-controls="upload-layer"
              >
                <Upload className="mr-3 h-4 w-4" aria-hidden />
                {t('upload-layer')}
              </Button>
            ) : null
          }
        </div>
      </div>
      <div className="mt-2 w-full px-5">
        {uploadError && (
          <p
            id="modelling-button-error"
            className="text-[11px] font-medium leading-4 text-error"
            role="alert"
          >
            {uploadError}
          </p>
        )}
      </div>
    </div>
  );
};

ModellingButtons.messages = ['containers.map-sidebar-main-panel'];

export default ModellingButtons;
