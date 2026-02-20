import { ChangeEventHandler, useCallback, useState } from 'react';

import { useSetAtom } from 'jotai';
import { Upload } from 'lucide-react';
import { useTranslations } from 'next-intl';

import TooltipButton from '@/components/tooltip-button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { CUSTOM_LAYER_STYLE_COLORS } from '@/constants/custom-layer-style-colors';
import { bboxLocationAtom, customLayersAtom } from '@/containers/map/store';
import { FileTooLargeError, useUploadErrorMessage } from '@/hooks/use-upload-error-message';
import { cn } from '@/lib/classnames';
import { convertFilesToGeojson, supportedFileformats } from '@/lib/utils/file-upload';
import { getGeoJSONBoundingBox } from '@/lib/utils/geo';
import { FCWithMessages } from '@/types';
import { CustomLayer } from '@/types/layers';

import { MAX_CUSTOM_LAYER_SIZE, SWITCH_LABEL_CLASSES } from '../constants';

type UploadLayerProps = {
  isDisabled: boolean;
};

const DEFAULT_LAYER_STYLE = {
  opacity: 0.5,
};

const getNextCustomLayerColor = (layers: Record<string, CustomLayer>): string => {
  const nextColorIndex = Object.keys(layers).length % CUSTOM_LAYER_STYLE_COLORS.length;
  return CUSTOM_LAYER_STYLE_COLORS[nextColorIndex].value;
};

const UploadLayer: FCWithMessages<UploadLayerProps> = ({ isDisabled }) => {
  const t = useTranslations('containers.map-sidebar-layers-panel');
  const getUploadErrorMessage = useUploadErrorMessage({
    maxFileSize: MAX_CUSTOM_LAYER_SIZE,
  });
  const setBboxLocation = useSetAtom(bboxLocationAtom);
  const setCustomLayers = useSetAtom(customLayersAtom);

  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const onChange: ChangeEventHandler<HTMLInputElement> = useCallback(
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
          const newId = window.crypto.randomUUID();

          setErrorMessage(null);
          setCustomLayers((prev) => {
            const color = getNextCustomLayerColor(prev);

            return {
              ...prev,
              [newId]: {
                id: newId,
                name: files[0]?.name ?? '',
                feature: geojson,
                isVisible: true,
                isActive: true,
                style: {
                  ...DEFAULT_LAYER_STYLE,
                  fillColor: color,
                  lineColor: color,
                },
              },
            };
          });
          const bounds = getGeoJSONBoundingBox(geojson);
          if (bounds) {
            setBboxLocation(bounds as [number, number, number, number]);
          }
        } catch (error) {
          setErrorMessage(getUploadErrorMessage(error));
        } finally {
          input.value = '';
        }
      })();
    },
    [setBboxLocation, setCustomLayers, getUploadErrorMessage]
  );

  return (
    <>
      <div className="flex items-start justify-between">
        <Label
          htmlFor="upload-layer"
          className={cn(SWITCH_LABEL_CLASSES, 'flex items-center gap-2 pb-2', {
            'text-gray-500': isDisabled,
          })}
        >
          <Input
            id="upload-layer"
            type="file"
            multiple
            accept={supportedFileformats.map((ext) => `.${ext}`).join(',')}
            className="hidden"
            onChange={onChange}
            disabled={isDisabled}
          />
          <button
            type="button"
            onClick={() => document.getElementById('upload-layer')?.click()}
            className={cn(SWITCH_LABEL_CLASSES, 'flex items-center gap-2')}
            disabled={isDisabled}
          >
            <Upload size={18} />
            <span>{t('upload-layer')}</span>
          </button>
        </Label>
        <TooltipButton className="ml-auto mt-px" text={t('upload-directions')} />
      </div>
      <p className="text-error">{errorMessage}</p>
    </>
  );
};

UploadLayer.messages = ['containers.map-sidebar-layers-panel'];

export default UploadLayer;
