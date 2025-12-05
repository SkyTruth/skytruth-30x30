import { ChangeEvent, ChangeEventHandler, useCallback, useState } from 'react';
import { useSetAtom } from "jotai";

import { convertFilesToGeojson, supportedFileformats } from '@/lib/utils/file-upload';

import { drawStateAtom } from "@/containers/map/store";

import { Button } from "@/components/ui/button";
import { Input } from '@/components/ui/input';
import { Upload } from "lucide-react";

import { cn } from "@/lib/classnames";


const UploadLayer = () => {
  const setDrawState = useSetAtom(drawStateAtom);
    const [errorMessage, setErrorMessage] = useState<string | null>(null);

    const onChange: ChangeEventHandler<HTMLInputElement> = useCallback(
      (e) => {
        const handler = async (e: ChangeEvent<HTMLInputElement>) => {
          const { files } = e.currentTarget;

          try {
            const geojson = await convertFilesToGeojson(Array.from(files));
            setErrorMessage(null);
            setDrawState({ active: false, feature: geojson, status: 'success' });
          } catch (errorMessage) {
            setErrorMessage(errorMessage as string);
          }
        };

        void handler(e);
      },
      [setDrawState]
    );

  const BUTTON_CLASSES =
  'font-mono text-xs font-semibold no-underline normal-case ring-offset-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-black focus-visible:ring-offset-2 transition-all px-0 text-left h-auto justify-start py-0';


  return (
    <Button
          className={cn({
            [BUTTON_CLASSES]: true,
          })}
          type="button"
          variant="text-link"
          onClick={() => console.log("Clciked uplaod!")}
        >
           <Input
          type="file"
          multiple
          accept={supportedFileformats.map((ext) => `.${ext}`).join(',')}
          aria-label="Upload a geometry"
          aria-describedby="upload-notes upload-error"
          className="mt-8"
          onChange={onChange}
        />
          <Upload
            className='ease-&lsqb;cubic-bezier(0.87,_0,_0.13,_1)&rsqb; mr-2 h-4 w-4 pb-px transition-transform duration-300'
          />
          Upload layer
        </Button>
  )
}

export default UploadLayer