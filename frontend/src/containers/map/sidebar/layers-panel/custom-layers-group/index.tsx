import { PropsWithChildren, useCallback, useState, useMemo } from 'react';

import { useAtom } from 'jotai';
import { useTranslations } from 'next-intl';
import { LuChevronDown, LuChevronUp } from 'react-icons/lu';
import { Trash } from 'lucide-react';

import TooltipButton from '@/components/tooltip-button';
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible';
import { Label } from '@/components/ui/label';
import { Switch } from '@/components/ui/switch';
import { allActiveLayersAtom, customLayersAtom } from '@/containers/map/store';
import { cn } from '@/lib/classnames';
import { FCWithMessages } from '@/types';
import { CustomLayer } from '@/types/layers';
import { Button } from '@/components/ui/button';

import UploadLayer from '../../main-panel/panels/details/upload-layer';

export const SWITCH_LABEL_CLASSES = '-mb-px cursor-pointer pt-px font-mono text-xs font-normal';
const COLLAPSIBLE_TRIGGER_ICONS_CLASSES = 'w-5 h-5 hidden';
const COLLAPSIBLE_TRIGGER_CLASSES =
  'group flex w-full items-center justify-between py-2 text-xs font-bold';
const COLLAPSIBLE_CONTENT_CLASSES =
  'data-[state=closed]:animate-collapsible-up data-[state=open]:animate-collapsible-down border-black';

type CustomLayersGroupProps = PropsWithChildren<{
  name: string;
  showDatasetsNames?: boolean;
  showBottomBorder?: boolean;
  isOpen?: boolean;
  loading?: boolean;
  // Number of extra active layers for this group
  extraActiveLayers?: number;
}>;

const CustomLayersGroup: FCWithMessages<CustomLayersGroupProps> = ({
  name,
  showDatasetsNames = true,
  showBottomBorder = true,
  isOpen = true,
  loading = true,
  extraActiveLayers = 0,
  children,
}): JSX.Element => {
  const [open, setOpen] = useState(isOpen);
  const t = useTranslations('containers.map-sidebar-layers-panel');

  const [customLayers, setCustomLayers] = useAtom(customLayersAtom);
  const [allActiveLayers, setAllActiveLayers] = useAtom(allActiveLayersAtom);

  const numActiveDatasetsLayers = useMemo(() => {
    return Object.keys(customLayers).length + extraActiveLayers;
  }, [customLayers, extraActiveLayers]);

  const onToggleLayer = useCallback(
    (toggled: CustomLayer, checked: boolean) => {
      const updatedLayers = { ...customLayers };
      let updatedActiveLayers = [...allActiveLayers];
      updatedLayers[toggled.id].isActive = checked;

      if (checked) {
        updatedActiveLayers.unshift(toggled.id);
      } else {
        updatedActiveLayers = updatedActiveLayers.filter((id) => id !== toggled.id);
      }

      setCustomLayers(updatedLayers);
      setAllActiveLayers(updatedActiveLayers);
    },
    [allActiveLayers, customLayers, setAllActiveLayers, setCustomLayers]
  );

  const onDeleteLayer = useCallback((slug: string) => {
    const updatedLayers = {...customLayers};
    delete updatedLayers[slug];

    setCustomLayers(updatedLayers);
  }, [customLayers, setCustomLayers])

  const displayNumActiveLayers = !open && numActiveDatasetsLayers > 0;

  return (
    <Collapsible open={open} onOpenChange={setOpen}>
      <CollapsibleTrigger
        className={cn(COLLAPSIBLE_TRIGGER_CLASSES, { 'border-b border-black': !open })}
      >
        <span>
          {name}
          {displayNumActiveLayers && (
            <span className="ml-2 border border-black px-1 font-normal">
              {numActiveDatasetsLayers}
            </span>
          )}
        </span>
        <LuChevronDown
          className={`group-data-[state=closed]:block ${COLLAPSIBLE_TRIGGER_ICONS_CLASSES}`}
        />
        <LuChevronUp
          className={`group-data-[state=open]:block ${COLLAPSIBLE_TRIGGER_ICONS_CLASSES}`}
        />
      </CollapsibleTrigger>
      <CollapsibleContent
        className={cn(COLLAPSIBLE_CONTENT_CLASSES, { 'border-b': showBottomBorder })}
      >
        <div>
          {loading && <span className="font-mono text-xs">{t('loading')}</span>}
          <UploadLayer />
          <div>
            <ul className={cn('my-3 flex flex-col space-y-3', { '-my-0': !showDatasetsNames })}>
              {Object.keys(customLayers).map((slug) => {
                const layer = customLayers[slug];
                const isActive = layer.isActive;

                return (
                  <li key={layer.name} className="flex items-start justify-between">
                    <span className="flex items-start gap-2">
                      <Switch
                        id={`${layer.name}-switch`}
                        className="mt-px"
                        checked={isActive}
                        onCheckedChange={() => onToggleLayer(layer, !isActive)}
                      />
                      <Label htmlFor={`${layer.name}-switch`} className={SWITCH_LABEL_CLASSES}>
                        {layer.name}
                      </Label>
                    </span>
                    <button 
                      aria-label={t('delete-layer', {layer: layer.name})}
                      onClick={() => onDeleteLayer(slug)}  
                    >
                      <Trash size={16} />
                    </button>
                    {/* {metadata?.description && (
                          <TooltipButton
                            className="mt-px"
                            text={metadata?.description}
                            sources={sources}
                          />
                        )} */}
                  </li>
                );
              })}
              <>{children}</>
            </ul>
          </div>
        </div>
      </CollapsibleContent>
    </Collapsible>
  );
};

CustomLayersGroup.messages = ['containers.map-sidebar-layers-panel', ...TooltipButton.messages];

export default CustomLayersGroup;
