import { ChangeEvent, ChangeEventHandler, useCallback, useState } from 'react';

import { useAtom } from 'jotai';
import { Upload } from 'lucide-react';

// import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { SWITCH_LABEL_CLASSES } from '@/containers/map/sidebar/layers-panel/layers-group';
import { userLayersAtom } from '@/containers/map/store';
// import { cn } from '@/lib/classnames';
import { convertFilesToGeojson, supportedFileformats } from '@/lib/utils/file-upload';

const UploadLayer = () => {
  const [userLayers, setUserLayers] = useAtom(userLayersAtom);
  // Remove this
  // eslint-disable-next-line
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const onChange: ChangeEventHandler<HTMLInputElement> = useCallback(
    (e) => {
      const handler = async (e: ChangeEvent<HTMLInputElement>) => {
        const { files } = e.currentTarget;
        try {
          const geojson = await convertFilesToGeojson(Array.from(files));
          setErrorMessage(null);
          setUserLayers([...userLayers, { name: files[0].name, geoJSON: geojson }]);
        } catch (errorMessage) {
          setErrorMessage(errorMessage as string);
        }
      };

      void handler(e);
    },
    [setUserLayers, userLayers]
  );

  // const BUTTON_CLASSES =
  // 'font-mono text-xs font-semibold no-underline normal-case ring-offset-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-black focus-visible:ring-offset-2 transition-all px-0 text-left h-auto justify-start py-0';

  return (
    //  <Button
    //   className={cn({
    //     [BUTTON_CLASSES]: true,
    //   })}
    //   type="button"
    //   variant="text-link"
    //   onClick={() => {}}
    // >
    //@ts-ignore
    <Label htmlFor="upload-layer" className={SWITCH_LABEL_CLASSES}>
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
    </Label>
    // </Button>
  );
};

export default UploadLayer;
