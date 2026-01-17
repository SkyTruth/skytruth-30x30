import { PropsWithChildren, useCallback, useEffect, useMemo, useRef, useState } from 'react';

import { useAtom } from 'jotai';
import { Trash } from 'lucide-react';
import { useTranslations } from 'next-intl';
import { LuChevronDown, LuChevronUp } from 'react-icons/lu';

import TooltipButton from '@/components/tooltip-button';
import { Button } from '@/components/ui/button';
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible';
import { Label } from '@/components/ui/label';
import { Switch } from '@/components/ui/switch';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip';
import { allActiveLayersAtom, customLayersAtom } from '@/containers/map/store';
import { cn } from '@/lib/classnames';
import { FCWithMessages } from '@/types';
import { CustomLayer } from '@/types/layers';

import {
  COLLAPSIBLE_TRIGGER_ICONS_CLASSES,
  COLLAPSIBLE_TRIGGER_CLASSES,
  COLLAPSIBLE_CONTENT_CLASSES,
  SWITCH_LABEL_CLASSES,
  MAX_CUSTOM_LAYERS,
} from '../constants';
import UploadLayer from '../upload-layer';

type CustomLayersGroupProps = PropsWithChildren<{
  name: string;
  showBottomBorder?: boolean;
  isOpen?: boolean;
}>;

const CustomLayersGroup: FCWithMessages<CustomLayersGroupProps> = ({
  name,
  showBottomBorder = true,
  isOpen = true,
  children,
}): JSX.Element => {
  const t = useTranslations('containers.map-sidebar-layers-panel');

  const [open, setOpen] = useState(isOpen);
  const [editingSlug, setEditingSlug] = useState<string | null>(null);
  const [draftName, setDraftName] = useState<string>('');

  const inputRef = useRef<HTMLInputElement | null>(null);

  const [customLayers, setCustomLayers] = useAtom(customLayersAtom);
  const [allActiveLayers, setAllActiveLayers] = useAtom(allActiveLayersAtom);

  useEffect(() => {
    if (editingSlug) {
      requestAnimationFrame(() => inputRef.current?.focus());
    }
  }, [editingSlug]);

  const numCustomLayers = useMemo(() => {
    return Object.keys(customLayers).length;
  }, [customLayers]);

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

  const onDeleteLayer = useCallback(
    (slug: string) => {
      const updatedLayers = { ...customLayers };
      delete updatedLayers[slug];

      setCustomLayers(updatedLayers);
    },
    [customLayers, setCustomLayers]
  );

  const onRenameLayer = useCallback(
    (slug: string, newName: string) => {
      setCustomLayers((prev) => {
        prev[slug].name = newName;
        return {
          ...prev,
        };
      });
    },
    [setCustomLayers]
  );

  const beginEdit = (slug: string, currentName: string) => {
    setEditingSlug(slug);
    setDraftName(currentName);
  };

  const cancelEdit = () => {
    setEditingSlug(null);
    setDraftName('');
  };

  const commitEdit = (slug: string) => {
    const next = draftName.trim();
    if (next.length === 0) return cancelEdit();

    if (customLayers[slug]?.name !== next) {
      onRenameLayer(slug, next);
    }
    cancelEdit();
  };

  const isUploadDisabled = useMemo(() => {
    return Object.keys(customLayers).length >= MAX_CUSTOM_LAYERS;
  }, [customLayers]);

  const displayNumLayers = numCustomLayers > 0;

  return (
    <Collapsible open={open} onOpenChange={setOpen}>
      <CollapsibleTrigger
        className={cn(COLLAPSIBLE_TRIGGER_CLASSES, { 'border-b border-black': !open })}
      >
        <span>
          {name}
          {displayNumLayers && (
            <span className="ml-2 border border-black px-1 font-normal">{numCustomLayers}</span>
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
        className={cn(COLLAPSIBLE_CONTENT_CLASSES, {
          'border-b': showBottomBorder,
          'py-0': true,
        })}
      >
        <div>
          <UploadLayer isDisabled={isUploadDisabled} />
          <div className="pt3">
            <ul className={'my-3 flex flex-col space-y-3'}>
              {Object.keys(customLayers).map((slug) => {
                const layer = customLayers[slug];
                const isActive = layer.isActive;
                const isEditing = editingSlug === slug;

                return (
                  <li key={slug} className="flex items-start justify-between">
                    <span className="flex items-start gap-2 overflow-x-hidden text-nowrap">
                      <Switch
                        id={`${layer.name}-switch`}
                        aria-label={layer.name}
                        className="mt-px"
                        checked={isActive}
                        onCheckedChange={() => onToggleLayer(layer, !isActive)}
                      />

                      <div className="max-w-full">
                        {isEditing ? (
                          <div className="flex items-center gap-2">
                            <input
                              ref={inputRef}
                              value={draftName}
                              onChange={(e) => setDraftName(e.target.value)}
                              onKeyDown={(e) => {
                                if (e.key === 'Enter') commitEdit(slug);
                                if (e.key === 'Escape') cancelEdit();
                              }}
                              onBlur={() => commitEdit(slug)}
                              aria-label={t('edit-layer-name', { layer: layer.name })}
                              className={cn(
                                'w-full rounded-md border border-black bg-white px-2 py-1 text-sm',
                                'focus:outline-none focus:ring-2 focus:ring-black/30'
                              )}
                            />
                          </div>
                        ) : (
                          <Label
                            htmlFor={`${layer.name}-switch`}
                            className={cn(SWITCH_LABEL_CLASSES)}
                          >
                            <button
                              type="button"
                              className="hover:bg-gray-200 hover:text-gray-700 focus-visible:ring-black"
                              onClick={() => beginEdit(slug, layer.name)}
                            >
                              <span className="sr-only">{t('edit-layer-name')}</span>
                              {layer.name}
                            </button>
                          </Label>
                        )}
                      </div>
                    </span>

                    <TooltipProvider>
                      <div className="flex items-center">
                        <Tooltip delayDuration={0}>
                          <TooltipTrigger asChild>
                            <Button
                              className="h-auto w-auto pl-1.5"
                              type="button"
                              size="icon-sm"
                              variant="ghost"
                              onClick={() => onDeleteLayer(slug)}
                            >
                              <span className="sr-only">{t('delete-layer')}</span>
                              <Trash size={16} />
                            </Button>
                          </TooltipTrigger>
                          <TooltipContent>{t('delete-layer')}</TooltipContent>
                        </Tooltip>
                      </div>
                    </TooltipProvider>
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

CustomLayersGroup.messages = [
  'containers.map-sidebar-layers-panel',
  ...TooltipButton.messages,
  ...UploadLayer.messages,
];

export default CustomLayersGroup;
