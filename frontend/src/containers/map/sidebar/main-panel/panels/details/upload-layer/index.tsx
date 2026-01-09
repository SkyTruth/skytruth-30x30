import { ChangeEvent, ChangeEventHandler, useCallback, useState } from 'react';

import { useAtom } from 'jotai';
import { maxBy } from 'lodash-es';
import { Upload } from 'lucide-react';

// import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { SWITCH_LABEL_CLASSES } from '@/containers/map/sidebar/layers-panel/layers-group';
import { customLayersAtom } from '@/containers/map/store';
import { cn } from '@/lib/classnames';
import { convertFilesToGeojson, supportedFileformats } from '@/lib/utils/file-upload';

const UploadLayer = () => {
  const [customLayers, setCustomLayers] = useAtom(customLayersAtom);
  // Remove this
  // eslint-disable-next-line
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const onChange: ChangeEventHandler<HTMLInputElement> = useCallback(
    (e) => {
      const handler = async (e: ChangeEvent<HTMLInputElement>) => {
        const { files } = e.currentTarget;
        try {
          const geojson = await convertFilesToGeojson(Array.from(files));
          let newId = 0;

          if (customLayers.length) {
            const maxIdLayer = maxBy(customLayers, (layer) => layer.id);
            newId = maxIdLayer.id + 1;
          }

          setErrorMessage(null);
          setCustomLayers([
            ...customLayers,
            { id: newId, name: files[0].name, feature: geojson, active: true },
          ]);
        } catch (errorMessage) {
          setErrorMessage(errorMessage as string);
        }
      };

      void handler(e);
    },
    [setCustomLayers, customLayers]
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
        className="hidden"
        onChange={onChange}
      />
      <Upload size={18} />
      <span>Upload Layer</span>
    </Label>
  );
};

export default UploadLayer;
