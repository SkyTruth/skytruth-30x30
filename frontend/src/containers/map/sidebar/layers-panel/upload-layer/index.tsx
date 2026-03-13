import { ChangeEventHandler, useCallback, useState } from 'react';

import { useSetAtom } from 'jotai';
import { Upload } from 'lucide-react';
import { useTranslations } from 'next-intl';

import TooltipButton from '@/components/tooltip-button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { bboxLocationAtom, customLayersAtom } from '@/containers/map/store';
import { FileTooLargeError, useUploadErrorMessage } from '@/hooks/use-upload-error-message';
import { cn } from '@/lib/classnames';
import { createCustomLayer } from '@/lib/utils/create-custom-layer';
import {
  convertFilesToGeojson,
  extractPolygons,
  supportedFileformats,
} from '@/lib/utils/file-upload';
import { getGeoJSONBoundingBox } from '@/lib/utils/geo';
import { FCWithMessages } from '@/types';

import { MAX_CUSTOM_LAYER_SIZE, SWITCH_LABEL_CLASSES } from '../constants';

type UploadLayerProps = {
  isDisabled: boolean;
};

const UploadLayer: FCWithMessages<UploadLayerProps> = ({ isDisabled }) => {
  const t = useTranslations('containers.map-sidebar-layers-panel');
  const getUploadErrorMessage = useUploadErrorMessage({
    maxFileSize: MAX_CUSTOM_LAYER_SIZE,
  });
  const setBboxLocation = useSetAtom(bboxLocationAtom);
  const setCustomLayers = useSetAtom(customLayersAtom);

  const [uploadError, setUploadError] = useState<unknown>(null);

  const errorMessage = uploadError ? getUploadErrorMessage(uploadError) : null;

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

          let canBeUsedForModelling = false;
          try {
            extractPolygons(geojson);
            canBeUsedForModelling = true;
          } catch {
            // No polygon geometry — layer still renders, just can't be used for modelling
          }

          setUploadError(null);
          setCustomLayers((prev) => {
            const layer = createCustomLayer(
              files[0]?.name ?? '',
              geojson,
              prev,
              canBeUsedForModelling
            );
            return {
              ...prev,
              [layer.id]: layer,
            };
          });
          const bounds = getGeoJSONBoundingBox(geojson);
          if (bounds) {
            setBboxLocation(bounds as [number, number, number, number]);
          }
        } catch (error) {
          setUploadError(error);
        } finally {
          input.value = '';
        }
      })();
    },
    [setBboxLocation, setCustomLayers]
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
