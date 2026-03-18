import { useEffect, useRef, useState } from 'react';

import { AlertTriangle, BarChart4, Save, Trash } from 'lucide-react';
import { useTranslations } from 'next-intl';

import { Button } from '@/components/ui/button';
import { Label } from '@/components/ui/label';
import { Switch } from '@/components/ui/switch';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip';
import { cn } from '@/lib/classnames';
import { FCWithMessages } from '@/types';
import { CustomLayer } from '@/types/layers';

type CustomLayerItemProps = {
  slug: string;
  layer: CustomLayer;
  isActive: boolean;
  switchLabelClassName: string;
  saveTooltipLabel: string;
  isSaveDisabled: boolean;
  isUseForModellingDisabled: boolean;
  canBeUsedForModelling: boolean;
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
  isUseForModellingDisabled,
  canBeUsedForModelling,
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
  const useForModellingLabel = isUseForModellingDisabled
    ? t('layer-used-in-modelling')
    : t('use-layer-for-modelling');

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
        <span className="flex min-w-0 flex-1 items-start gap-2 text-nowrap">
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
                      className={cn(
                        'block w-full max-w-full cursor-text overflow-hidden text-ellipsis whitespace-nowrap text-left hover:bg-gray-200 hover:text-gray-700 focus-visible:ring-black',
                        isUseForModellingDisabled && 'font-bold'
                      )}
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
          {canBeUsedForModelling ? (
            <Tooltip delayDuration={0}>
              <TooltipTrigger asChild>
                <span className="inline-flex">
                  <Button
                    className={cn(
                      'h-auto w-auto pl-1.5',
                      isUseForModellingDisabled && 'disabled:opacity-100'
                    )}
                    type="button"
                    size="icon-sm"
                    variant="ghost"
                    disabled={isUseForModellingDisabled}
                    onClick={() => onUseLayerForModelling(layer)}
                  >
                    <span className="sr-only">{useForModellingLabel}</span>
                    <BarChart4
                      size={16}
                      strokeWidth={isUseForModellingDisabled ? 2.25 : 2}
                      className={cn(isUseForModellingDisabled && 'text-blue-600')}
                    />
                  </Button>
                </span>
              </TooltipTrigger>
              <TooltipContent>{useForModellingLabel}</TooltipContent>
            </Tooltip>
          ) : (
            <Tooltip delayDuration={0}>
              <TooltipTrigger asChild>
                <span className="inline-flex py-1 pl-1.5 text-gray-400">
                  <AlertTriangle size={16} />
                  <span className="sr-only">{t('invalid-geometry-for-stats')}</span>
                </span>
              </TooltipTrigger>
              <TooltipContent>{t('invalid-geometry-for-stats')}</TooltipContent>
            </Tooltip>
          )}
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
