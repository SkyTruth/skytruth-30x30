import { ChangeEvent, ChangeEventHandler, useCallback, useState } from 'react';

import { useAtom } from 'jotai';
import { maxBy } from 'lodash-es';
import { Upload } from 'lucide-react';

import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { SWITCH_LABEL_CLASSES } from '@/containers/map/sidebar/layers-panel/layers-group';
import { allActiveLayersAtom, customLayersAtom } from '@/containers/map/store';
import { cn } from '@/lib/classnames';
import { convertFilesToGeojson, supportedFileformats } from '@/lib/utils/file-upload';

const UploadLayer = () => {
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
          let newId = '0';
          const customLayerIds = Object.keys(customLayers);

          if (customLayerIds.length) {
            const maxIdLayer = maxBy(customLayerIds, (id) => +id);
            newId = (+maxIdLayer + 1).toString();
          }

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
        } catch (errorMessage) {
          setErrorMessage(errorMessage as string);
        }
      };

      void handler(e);
    },
    [allActiveLayers, customLayers, setAllActiveLayers, setCustomLayers]
  );

  return (
    <Label htmlFor="upload-layer" className={cn(SWITCH_LABEL_CLASSES, 'flex items-center gap-2')}>
      <Input
        id="upload-layer"
        type="file"
        multiple
        accept={supportedFileformats.map((ext) => `.${ext}`).join(',')}
        aria-label="Upload a geometry"
        aria-describedby="upload-notes upload-error"
        className="sr-only"
        onChange={onChange}
      />
      <button
        type="button"
        onClick={() => document.getElementById('upload-layer')?.click()}
        className={cn(SWITCH_LABEL_CLASSES, 'flex items-center gap-2')}
      >
        <Upload size={18} />
        <span>Upload Layer</span>
      </button>
    </Label>
  );
};

export default UploadLayer;
