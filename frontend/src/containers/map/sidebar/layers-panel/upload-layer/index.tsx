import { ChangeEventHandler, useCallback, useState } from 'react';

import { useAtom } from 'jotai';
import { Upload } from 'lucide-react';
import { useTranslations } from 'next-intl';

import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { customLayersAtom } from '@/containers/map/store';
import { cn } from '@/lib/classnames';
import {
  convertFilesToGeojson,
  supportedFileformats,
  UploadErrorType,
} from '@/lib/utils/file-upload';
import { FCWithMessages } from '@/types';

import { MAX_CUSTOM_LAYER_SIZE, SWITCH_LABEL_CLASSES } from '../constants';

type UploadLayerProps = {
  isDisabled: boolean;
};

const DEFAULT_LAYER_STYLE = {
  opacity: 0.5,
  fillColor: '#5278d1',
  lineColor: '#000000',
};

class FileTooLargeError extends Error {
  constructor(message?: string) {
    super(message ?? 'File too Large');
    this.name = 'FileTooLargeError';
  }
}

const UploadLayer: FCWithMessages<UploadLayerProps> = ({ isDisabled }) => {
  const t = useTranslations('containers.map-sidebar-layers-panel');
  const tUploads = useTranslations('services.uploads');
  const [customLayers, setCustomLayers] = useAtom(customLayersAtom);

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
          setCustomLayers({
            ...customLayers,
            [newId]: {
              id: newId,
              name: files[0]?.name ?? '',
              feature: geojson,
              isVisible: true,
              isActive: true,
              style: { ...DEFAULT_LAYER_STYLE },
            },
          });

          // New layers get activated and at the top of the stack
        } catch (error) {
          if (error instanceof FileTooLargeError) {
            setErrorMessage(
              tUploads('file-too-large-error', { size: `${MAX_CUSTOM_LAYER_SIZE / 1000000}Mb` })
            );
          } else {
            switch (error) {
              case UploadErrorType.InvalidXMLSyntax:
                setErrorMessage(tUploads('xml-syntax-error'));
                break;
              case UploadErrorType.SHPMissingFile:
                setErrorMessage(tUploads('shp-missing-files-error'));
                break;
              case UploadErrorType.UnsupportedFile:
                setErrorMessage(tUploads('unsupported-file-error'));
                break;
              default:
                setErrorMessage(tUploads('generic-upload-error'));
                break;
            }
          }
        } finally {
          input.value = '';
        }
      })();
    },
    [customLayers, setCustomLayers, tUploads]
  );

  return (
    <>
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
      <p className="text-error">{errorMessage}</p>
    </>
  );
};

UploadLayer.messages = ['containers.map-sidebar-layers-panel', 'services.uploads'];

export default UploadLayer;
