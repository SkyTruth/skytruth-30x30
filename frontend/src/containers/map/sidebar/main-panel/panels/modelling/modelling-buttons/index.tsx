import { ChangeEventHandler, useCallback, useRef, useState } from 'react';

import { useAtom, useSetAtom } from 'jotai';
import { useResetAtom } from 'jotai/utils';
import { Upload } from 'lucide-react';
import { useTranslations } from 'next-intl';
import { LuTrash2 } from 'react-icons/lu';
import { RxTransform } from 'react-icons/rx';

import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { MAX_CUSTOM_LAYER_SIZE } from '@/containers/map/sidebar/layers-panel/constants';
import { bboxLocationAtom, modellingAtom, drawStateAtom } from '@/containers/map/store';
import { useFeatureFlag } from '@/hooks/use-feature-flag'; // TECH-3372: tear down
import { FileTooLargeError, useUploadErrorMessage } from '@/hooks/use-upload-error-message';
import { cn } from '@/lib/classnames';
import {
  extractPolygons,
  convertFilesToGeojson,
  supportedFileformats,
} from '@/lib/utils/file-upload';
import { getGeoJSONBoundingBox } from '@/lib/utils/geo';
import { FCWithMessages } from '@/types';

const COMMON_BUTTON_CLASSES =
  'flex h-10 justify-between border-t border-black px-5 md:px-8 w-full pt-1 font-mono text-xs normal-case justify-center';

type ModellingButtonsProps = {
  className?: HTMLDivElement['className'];
};

const ModellingButtons: FCWithMessages<ModellingButtonsProps> = ({ className }) => {
  const t = useTranslations('containers.map-sidebar-main-panel');
  const tUploads = useTranslations('services.uploads');
  const getUploadErrorMessage = useUploadErrorMessage({
    maxFileSize: MAX_CUSTOM_LAYER_SIZE,
  });
  // TECH-3372: tear down
  const isCustomLayersActive = useFeatureFlag('is_custom_layers_active');

  const [modellingState, setModelling] = useAtom(modellingAtom);
  const { status: modellingStatus } = modellingState;
  const setBboxLocation = useSetAtom(bboxLocationAtom);
  const resetModelling = useResetAtom(modellingAtom);
  const resetDrawState = useResetAtom(drawStateAtom);
  const [drawState, setDrawState] = useAtom(drawStateAtom);
  const { active, status, source } = drawState;

  const [uploadErrorMessage, setUploadErrorMessage] = useState<string | null>(null);
  const [uploadInfoMessage, setUploadInfoMessage] = useState<string | null>(null);
  const uploadInputRef = useRef<HTMLInputElement | null>(null);

  const onClickClearModelling = useCallback(() => {
    resetDrawState();
    resetModelling();
    setUploadErrorMessage(null);
    setUploadInfoMessage(null);
  }, [resetModelling, resetDrawState]);

  const onClickRedraw = useCallback(() => {
    resetModelling();
    setDrawState((prevState) => ({
      ...prevState,
      active: true,
      status: 'drawing',
      feature: null,
      source: 'draw',
    }));

    setModelling((prevState) => ({ ...prevState, active: true }));
    setUploadErrorMessage(null);
    setUploadInfoMessage(null);
  }, [resetModelling, setModelling, setDrawState]);

  const onUploadChange: ChangeEventHandler<HTMLInputElement> = useCallback(
    (event) => {
      const input = event.currentTarget;
      const files = Array.from(input.files ?? []);
      const previousDrawState = drawState;
      void (async () => {
        if (files.length === 0) {
          return;
        }

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
          const { feature, removed } = extractPolygons(geojson);

          if (!feature) {
            throw new Error('No valid geometry found');
          }

          setDrawState((prevState) => ({
            ...prevState,
            active: false,
            status: 'success',
            feature,
            revision: prevState.revision + 1,
            source: 'upload',
          }));

          setModelling((prevState) => ({ ...prevState, active: true }));
          const bounds = getGeoJSONBoundingBox(feature);
          if (bounds) {
            setBboxLocation([...bounds] as [number, number, number, number]);
          }
          setUploadErrorMessage(null);
          setUploadInfoMessage(removed.any ? tUploads('features-excluded-info') : null);
        } catch (error) {
          setDrawState(previousDrawState);
          setUploadInfoMessage(null);
          setUploadErrorMessage(getUploadErrorMessage(error));
        } finally {
          input.value = '';
        }
      })();
    },
    [
      drawState,
      setDrawState,
      setModelling,
      setBboxLocation,
      getUploadErrorMessage,
      setUploadErrorMessage,
      setUploadInfoMessage,
      tUploads,
    ]
  );

  const onOpenUploadPicker = useCallback(() => {
    uploadInputRef.current?.click();
  }, []);

  const isUploadProcessing = status === 'uploading';
  const isUploadDisabled =
    active || status === 'drawing' || status === 'uploading' || modellingStatus === 'running';
  const isDrawDisabled = isUploadProcessing;
  const ariaDescribedBy = [
    uploadErrorMessage ? 'upload-shape-error' : null,
    !uploadErrorMessage && uploadInfoMessage ? 'upload-shape-info' : null,
  ]
    .filter(Boolean)
    .join(' ');

  return (
    <div className={cn('flex w-full flex-col font-mono', className)}>
      {
        // TODO: TECH-3372 remove feature flag check
        isCustomLayersActive ? (
          <>
            <label htmlFor="upload-shape" className="sr-only">
              {t('upload-shape')}
            </label>
            <Input
              id="upload-shape"
              ref={uploadInputRef}
              type="file"
              multiple
              accept={supportedFileformats.map((ext) => `.${ext}`).join(',')}
              className="hidden"
              onChange={onUploadChange}
              disabled={isUploadDisabled}
              aria-describedby={ariaDescribedBy || undefined}
              aria-invalid={Boolean(uploadErrorMessage)}
            />
          </>
        ) : null
      }

      {status !== 'drawing' && status !== 'success' && (
        <div className="flex w-full flex-col space-y-2">
          <div className="flex w-full space-x-2">
            <Button
              className={COMMON_BUTTON_CLASSES}
              size="full"
              disabled={isDrawDisabled}
              onClick={() => {
                setUploadErrorMessage(null);
                setUploadInfoMessage(null);
                setDrawState((prevState) => ({ ...prevState, active: true }));
              }}
            >
              <RxTransform className="mr-3 h-4 w-4" aria-hidden />
              {active ? t('start-drawing-on-map') : t('draw-shape')}
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
                  aria-controls="upload-shape"
                >
                  <Upload className="mr-3 h-4 w-4" aria-hidden />
                  {t('upload-shape')}
                </Button>
              ) : null
            }
          </div>
        </div>
      )}
      {(status === 'drawing' || status === 'success') && (
        <div className="flex w-full space-x-2">
          <Button
            variant="blue"
            className={COMMON_BUTTON_CLASSES}
            size="full"
            disabled={isUploadProcessing}
            onClick={onClickClearModelling}
          >
            <LuTrash2 className="mr-3 h-4 w-4" aria-hidden />
            {t('clear-shape')}
          </Button>
          <Button
            variant="blue"
            className={COMMON_BUTTON_CLASSES}
            size="full"
            disabled={isUploadProcessing}
            onClick={() => {
              if (source === 'upload' && isCustomLayersActive) {
                setUploadErrorMessage(null);
                setUploadInfoMessage(null);
                onOpenUploadPicker();
                return;
              }

              onClickRedraw();
            }}
          >
            {source === 'upload' && isCustomLayersActive ? (
              <Upload className="mr-3 h-4 w-4" aria-hidden />
            ) : (
              <RxTransform className="mr-3 h-4 w-4" aria-hidden />
            )}
            {source === 'upload' && isCustomLayersActive ? t('upload-new-shape') : t('re-draw')}
          </Button>
        </div>
      )}
      <div className="mt-2 w-full">
        {uploadErrorMessage && (
          <p id="upload-shape-error" className="text-[11px] leading-4 text-error" role="alert">
            {uploadErrorMessage}
          </p>
        )}
        {!uploadErrorMessage && uploadInfoMessage && (
          <p
            id="upload-shape-info"
            className="text-[11px] leading-4 text-black"
            role="status"
            aria-live="polite"
          >
            {uploadInfoMessage}
          </p>
        )}
      </div>
    </div>
  );
};

ModellingButtons.messages = ['containers.map-sidebar-main-panel', 'services.uploads'];

export default ModellingButtons;
