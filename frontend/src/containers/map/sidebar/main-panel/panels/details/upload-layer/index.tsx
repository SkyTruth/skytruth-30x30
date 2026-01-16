import { ChangeEvent, ChangeEventHandler, useCallback, useState } from 'react';

import { useAtom } from 'jotai';
import { Upload } from 'lucide-react';
import { useTranslations } from 'next-intl';

import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { SWITCH_LABEL_CLASSES } from '@/containers/map/sidebar/layers-panel/layers-group';
import { allActiveLayersAtom, customLayersAtom } from '@/containers/map/store';
import { cn } from '@/lib/classnames';
import {
  convertFilesToGeojson,
  supportedFileformats,
  UploadErrorType,
} from '@/lib/utils/file-upload';
import { FCWithMessages } from '@/types';

type UploadLayerProps = {
  isDisabled: boolean;
};

const UploadLayer: FCWithMessages<UploadLayerProps> = ({ isDisabled }) => {
  const t = useTranslations('containers.map-sidebar-layers-panel');
  const [customLayers, setCustomLayers] = useAtom(customLayersAtom);
  const [allActiveLayers, setAllActiveLayers] = useAtom(allActiveLayersAtom);
  // Remove this
  // eslint-disable-next-line
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const onChange: ChangeEventHandler<HTMLInputElement> = useCallback(
    (e) => {
      const handler = async (e: ChangeEvent<HTMLInputElement>) => {
        const { files } = e.currentTarget;
        try {
          const geojson = await convertFilesToGeojson(Array.from(files));
          const newId = window.crypto.randomUUID();

          setErrorMessage(null);
          setCustomLayers({
            ...customLayers,
            [newId]: {
              id: newId,
              name: files[0].name,
              feature: geojson,
              isVisible: true,
              isActive: true,
              order: allActiveLayers.length - 1,
            },
          });

          // New layers get activated and at the top of the stack
          setAllActiveLayers([newId, ...allActiveLayers]);
        } catch (error) {
          switch (error) {
            case UploadErrorType.InvalidXMLSyntax:
              setErrorMessage(t('xml-syntax-error'));
              break;
            case UploadErrorType.SHPMissingFile:
              setErrorMessage(t('shp-missing-files-error'));
              break;
            case UploadErrorType.UnsupportedFile:
              setErrorMessage(t('unsupported-file-error'));
              break;
            default:
              setErrorMessage(t('generic-upload-error'));
              break;
          }
        }
      };

      void handler(e);
    },
    [allActiveLayers, customLayers, setAllActiveLayers, setCustomLayers, t]
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
          className="sr-only"
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

UploadLayer.messages = ['containers.map-sidebar-layers-panel'];

export default UploadLayer;
