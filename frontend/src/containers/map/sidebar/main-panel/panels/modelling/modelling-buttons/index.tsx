import { ChangeEventHandler, useCallback, useRef, useState } from 'react';

import { useAtom } from 'jotai';
import { useResetAtom } from 'jotai/utils';
import { useTranslations } from 'next-intl';
import { LuTrash2 } from 'react-icons/lu';
import { RxTransform } from 'react-icons/rx';

import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { MAX_CUSTOM_LAYER_SIZE } from '@/containers/map/sidebar/layers-panel/constants';
import { modellingAtom, drawStateAtom } from '@/containers/map/store';
import { cn } from '@/lib/classnames';
import {
  cleanupGeoJSON,
  convertFilesToGeojson,
  supportedFileformats,
} from '@/lib/utils/file-upload';
import { FileTooLargeError, useUploadErrorMessage } from '@/hooks/use-upload-error-message';
import { FCWithMessages } from '@/types';

const COMMON_BUTTON_CLASSES =
  'flex h-10 justify-between border-t border-black px-5 md:px-8 w-full pt-1 font-mono text-xs normal-case justify-center';

type ModellingButtonsProps = {
  className?: HTMLDivElement['className'];
};

const ModellingButtons: FCWithMessages<ModellingButtonsProps> = ({ className }) => {
  const t = useTranslations('containers.map-sidebar-main-panel');
  const getUploadErrorMessage = useUploadErrorMessage({
    maxFileSize: MAX_CUSTOM_LAYER_SIZE,
  });

  const [{ status: modellingStatus }, setModelling] = useAtom(modellingAtom);
  const resetModelling = useResetAtom(modellingAtom);
  const resetDrawState = useResetAtom(drawStateAtom);
  const [{ active, status, source }, setDrawState] = useAtom(drawStateAtom);

  const [uploadErrorMessage, setUploadErrorMessage] = useState<string | null>(null);
  const uploadInputRef = useRef<HTMLInputElement | null>(null);

  const onClickClearModelling = useCallback(() => {
    resetDrawState();
    resetModelling();
    setUploadErrorMessage(null);
  }, [resetModelling, resetDrawState]);

  const onClickRedraw = useCallback(() => {
    resetDrawState();
    resetModelling();
    setDrawState({
      active: true,
      status: 'drawing',
      feature: null,
    });

    setModelling((prevState) => ({ ...prevState, active: true }));
    setUploadErrorMessage(null);
  }, [resetModelling, resetDrawState, setModelling, setDrawState]);

  const onUploadChange: ChangeEventHandler<HTMLInputElement> = useCallback(
    (event) => {
      const input = event.currentTarget;
      const files = Array.from(input.files ?? []);
      void (async () => {
        if (files.length === 0) {
          return;
        }

        let totalSize = 0;
        for (const file of files) {
          totalSize += file.size;
        }

        try {
          if (totalSize > MAX_CUSTOM_LAYER_SIZE) {
            throw new FileTooLargeError();
          }

          const geojson = await convertFilesToGeojson(files);
          const feature = cleanupGeoJSON(geojson);

          if (!feature) {
            throw new Error('No valid geometry found');
          }

          setDrawState({
            active: false,
            status: 'success',
            feature,
            source: 'upload',
          });

          setModelling((prevState) => ({ ...prevState, active: true }));
          setUploadErrorMessage(null);
        } catch (error) {
          setUploadErrorMessage(getUploadErrorMessage(error));
        } finally {
          input.value = '';
        }
      })();
    },
    [setDrawState, setModelling, getUploadErrorMessage, setUploadErrorMessage]
  );

  const onOpenUploadPicker = useCallback(() => {
    uploadInputRef.current?.click();
  }, []);

  const isUploadDisabled = active || status === 'drawing' || modellingStatus === 'running';

  return (
    <div className={cn('flex font-mono', className)}>
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
        aria-describedby="upload-shape-error"
        aria-invalid={Boolean(uploadErrorMessage)}
      />

      {status !== 'drawing' && status !== 'success' && (
        <div className="flex w-full flex-col space-y-2">
          <div className="flex w-full space-x-2">
            <Button
              className={COMMON_BUTTON_CLASSES}
              size="full"
              onClick={() => {
                setUploadErrorMessage(null);
                setDrawState((prevState) => ({ ...prevState, active: true }));
              }}
            >
              <RxTransform className="mr-3 h-4 w-4" aria-hidden />
              {active ? t('start-drawing-on-map') : t('draw-shape')}
            </Button>
            <Button
              className={COMMON_BUTTON_CLASSES}
              size="full"
              type="button"
              onClick={onOpenUploadPicker}
              disabled={isUploadDisabled}
              aria-controls="upload-shape"
            >
              {t('upload-shape')}
            </Button>
          </div>
          {uploadErrorMessage && (
            <p id="upload-shape-error" className="text-error" role="alert">
              {uploadErrorMessage}
            </p>
          )}
        </div>
      )}
      {(status === 'drawing' || status === 'success') && (
        <div className="flex w-full space-x-2">
          <Button
            variant="blue"
            className={COMMON_BUTTON_CLASSES}
            size="full"
            onClick={onClickClearModelling}
          >
            <LuTrash2 className="mr-3 h-4 w-4" aria-hidden />
            {t('clear-shape')}
          </Button>
          <Button
            variant="blue"
            className={COMMON_BUTTON_CLASSES}
            size="full"
            onClick={() => {
              if (source === 'upload') {
                setUploadErrorMessage(null);
                onOpenUploadPicker();
                return;
              }

              onClickRedraw();
            }}
          >
            <RxTransform className="mr-3 h-4 w-4" aria-hidden />
            {source === 'upload' ? t('upload-new-shape') : t('re-draw')}
          </Button>
        </div>
      )}
    </div>
  );
};

ModellingButtons.messages = ['containers.map-sidebar-main-panel', 'services.uploads'];

export default ModellingButtons;
