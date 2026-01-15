import { PropsWithChildren, useCallback, useEffect, useMemo, useRef, useState } from 'react';

import { useAtom } from 'jotai';
import { Pencil, Trash } from 'lucide-react';
import { useTranslations } from 'next-intl';
import { LuChevronDown, LuChevronUp } from 'react-icons/lu';

import TooltipButton from '@/components/tooltip-button';
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible';
import { Label } from '@/components/ui/label';
import { Switch } from '@/components/ui/switch';
import { allActiveLayersAtom, customLayersAtom } from '@/containers/map/store';
import { cn } from '@/lib/classnames';
import { FCWithMessages } from '@/types';
import { CustomLayer } from '@/types/layers';

import UploadLayer from '../../main-panel/panels/details/upload-layer';

export const SWITCH_LABEL_CLASSES = '-mb-px cursor-pointer pt-px font-mono text-xs font-normal';
const COLLAPSIBLE_TRIGGER_ICONS_CLASSES = 'w-5 h-5 hidden';
const COLLAPSIBLE_TRIGGER_CLASSES =
  'group flex w-full items-center justify-between py-1 text-xs font-bold';
const COLLAPSIBLE_CONTENT_CLASSES =
  'data-[state=closed]:animate-collapsible-up data-[state=open]:animate-collapsible-down border-black';

const MAX_CUSTOM_LAYERS = 5;
export const MAX_CUSTOM_LAYER_SIZE = '5mb';

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
      // inputRef.current?.focus()
    }
  }, [editingSlug]);

  const numCustomLayers = useMemo(() => {
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

  const displayNumLayers = open && numCustomLayers > 0;

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
        className={cn(COLLAPSIBLE_CONTENT_CLASSES, { 'border-b': showBottomBorder })}
      >
        <div>
          {loading && <span className="font-mono text-xs">{t('loading')}</span>}
          <UploadLayer isDisabled={isUploadDisabled} />
          <div>
            <ul className={cn('my-3 flex flex-col space-y-3', { '-my-0': !showDatasetsNames })}>
              {Object.keys(customLayers).map((slug) => {
                const layer = customLayers[slug];
                const isActive = layer.isActive;
                const isEditing = editingSlug === slug;

                return (
                  <li key={slug} className="flex items-start justify-between gap-3">
                    <span className="flex min-w-0 flex-1 items-start gap-2 overflow-x-hidden">
                      <Switch
                        id={`${layer.name}-switch`}
                        className="mt-px"
                        checked={isActive}
                        onCheckedChange={() => onToggleLayer(layer, !isActive)}
                      />

                      <div className="min-w-0 flex-1">
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
                            className={cn(SWITCH_LABEL_CLASSES, 'overflow-x-hidden')}
                          >
                            {layer.name}
                          </Label>
                        )}
                      </div>
                    </span>

                    <button
                      type="button"
                      aria-label={t('edit-layer-name')}
                      onClick={() => (isEditing ? commitEdit(slug) : beginEdit(slug, layer.name))}
                      className={cn(isEditing ? 'border border-black bg-black/5' : '')}
                    >
                      <Pencil size={16} />
                    </button>

                    <button
                      type="button"
                      aria-label={t('delete-layer', { layer: layer.name })}
                      onClick={() => onDeleteLayer(slug)}
                    >
                      <Trash size={16} />
                    </button>
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
