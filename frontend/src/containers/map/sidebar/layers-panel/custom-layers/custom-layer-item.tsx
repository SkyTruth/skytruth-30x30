import { useEffect, useRef, useState } from 'react';

import { BarChartHorizontal, Save, Trash } from 'lucide-react';
import { useTranslations } from 'next-intl';

import { Button } from '@/components/ui/button';
import { Label } from '@/components/ui/label';
import { Switch } from '@/components/ui/switch';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip';
import { cn } from '@/lib/classnames';
import { FCWithMessages } from '@/types';
import { CustomLayer } from '@/types/layers';

// Taken from this SVG in Lucide React https://lucide.dev/icons/pencil
const PENCIL_CURSOR = `url("data:image/svg+xml,${encodeURIComponent(
  "<svg xmlns='http://www.w3.org/2000/svg' width='18' height='18' viewBox='0 0 24 24' fill='none' stroke='black' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'><path d='M17 3a2.85 2.83 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5Z'/><path d='m15 5 4 4'/></svg>"
)}") 2 16, pointer`;

type CustomLayerItemProps = {
  slug: string;
  layer: CustomLayer;
  isActive: boolean;
  switchLabelClassName: string;
  saveTooltipLabel: string;
  isSaveDisabled: boolean;
  onToggleLayer: (layer: CustomLayer, checked: boolean) => void;
  onCommitEdit: (slug: string, newName: string) => void;
  onSaveLayer: (layer: CustomLayer) => Promise<void> | void;
  onUseLayerForModelling: (layer: CustomLayer) => void;
  onDeleteLayer: (slug: string) => Promise<void> | void;
};

const CustomLayerItem: FCWithMessages<CustomLayerItemProps> = ({
  slug,
  layer,
  isActive,
  switchLabelClassName,
  saveTooltipLabel,
  isSaveDisabled,
  onToggleLayer,
  onCommitEdit,
  onSaveLayer,
  onUseLayerForModelling,
  onDeleteLayer,
}) => {
  const t = useTranslations('containers.map-sidebar-layers-panel');
  const [isEditing, setIsEditing] = useState(false);
  const [draftName, setDraftName] = useState(layer.name);
  const inputRef = useRef<HTMLInputElement | null>(null);

  useEffect(() => {
    if (isEditing) {
      requestAnimationFrame(() => inputRef.current?.focus());
    }
  }, [isEditing]);

  useEffect(() => {
    if (!isEditing) {
      setDraftName(layer.name);
    }
  }, [isEditing, layer.name]);

  const beginEdit = () => {
    setDraftName(layer.name);
    setIsEditing(true);
  };

  const cancelEdit = () => {
    setIsEditing(false);
    setDraftName(layer.name);
  };

  const commitEdit = () => {
    const next = draftName.trim();
    if (next.length === 0) {
      cancelEdit();
      return;
    }

    if (next !== layer.name) {
      onCommitEdit(slug, next);
    }
    setIsEditing(false);
  };

  return (
    <li className="flex items-start justify-between">
      <TooltipProvider>
        <span className="flex min-w-0 flex-1 items-start gap-2 overflow-x-hidden text-nowrap">
          <Switch
            id={`${layer.name}-switch`}
            aria-label={layer.name}
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
                  onChange={(event) => setDraftName(event.target.value)}
                  onKeyDown={(event) => {
                    if (event.key === 'Enter') commitEdit();
                    if (event.key === 'Escape') cancelEdit();
                  }}
                  onBlur={commitEdit}
                  aria-label={t('edit-layer-name', { layer: layer.name })}
                  className="w-full rounded-md border border-black bg-white px-2 py-1 text-sm focus:outline-none focus:ring-2 focus:ring-black/30"
                />
              </div>
            ) : (
              <Label
                htmlFor={`${layer.name}-switch`}
                className={cn(switchLabelClassName, 'block min-w-0')}
              >
                <Tooltip delayDuration={0}>
                  <TooltipTrigger asChild>
                    <button
                      type="button"
                      className="block w-full max-w-full overflow-hidden text-ellipsis whitespace-nowrap text-left hover:bg-gray-200 hover:text-gray-700 focus-visible:ring-black"
                      style={{ cursor: PENCIL_CURSOR }}
                      onClick={beginEdit}
                    >
                      <span className="sr-only">{t('edit-layer-name')}</span>
                      {layer.name}
                    </button>
                  </TooltipTrigger>
                  <TooltipContent
                    align="start"
                    className="max-w-[var(--radix-tooltip-trigger-width)]"
                  >
                    {t('edit')}
                  </TooltipContent>
                </Tooltip>
              </Label>
            )}
          </div>
        </span>

        <div className="flex items-center">
          <Tooltip delayDuration={0}>
            <TooltipTrigger asChild>
              <span className="inline-flex">
                <Button
                  className="h-auto w-auto pl-1.5"
                  type="button"
                  size="icon-sm"
                  variant="ghost"
                  disabled={isSaveDisabled}
                  onClick={() => void onSaveLayer(layer)}
                >
                  <span className="sr-only">{saveTooltipLabel}</span>
                  <Save size={16} />
                </Button>
              </span>
            </TooltipTrigger>
            <TooltipContent>{saveTooltipLabel}</TooltipContent>
          </Tooltip>
          <Tooltip delayDuration={0}>
            <TooltipTrigger asChild>
              <Button
                className="h-auto w-auto pl-1.5"
                type="button"
                size="icon-sm"
                variant="ghost"
                onClick={() => onUseLayerForModelling(layer)}
              >
                <span className="sr-only">{t('use-layer-for-modelling')}</span>
                <BarChartHorizontal size={16} />
              </Button>
            </TooltipTrigger>
            <TooltipContent>{t('use-layer-for-modelling')}</TooltipContent>
          </Tooltip>
          <Tooltip delayDuration={0}>
            <TooltipTrigger asChild>
              <Button
                className="h-auto w-auto pl-1.5"
                type="button"
                size="icon-sm"
                variant="ghost"
                onClick={() => void onDeleteLayer(slug)}
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
};

CustomLayerItem.messages = ['containers.map-sidebar-layers-panel'];

export default CustomLayerItem;
