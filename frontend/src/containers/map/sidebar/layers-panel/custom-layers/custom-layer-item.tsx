import { RefObject } from 'react';

import { BarChartHorizontal, Save, Trash } from 'lucide-react';
import { useTranslations } from 'next-intl';

import { Button } from '@/components/ui/button';
import { Label } from '@/components/ui/label';
import { Switch } from '@/components/ui/switch';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip';
import { FCWithMessages } from '@/types';
import { CustomLayer } from '@/types/layers';

type CustomLayerItemProps = {
  slug: string;
  layer: CustomLayer;
  isActive: boolean;
  isEditing: boolean;
  draftName: string;
  inputRef: RefObject<HTMLInputElement | null>;
  switchLabelClassName: string;
  saveTooltipLabel: string;
  isSaveDisabled: boolean;
  onToggleLayer: (layer: CustomLayer, checked: boolean) => void;
  onBeginEdit: (slug: string, currentName: string) => void;
  onDraftNameChange: (value: string) => void;
  onCommitEdit: (slug: string) => void;
  onCancelEdit: () => void;
  onSaveLayer: (layer: CustomLayer) => Promise<void> | void;
  onUseLayerForModelling: (layer: CustomLayer) => void;
  onDeleteLayer: (slug: string) => Promise<void> | void;
};

const CustomLayerItem: FCWithMessages<CustomLayerItemProps> = ({
  slug,
  layer,
  isActive,
  isEditing,
  draftName,
  inputRef,
  switchLabelClassName,
  saveTooltipLabel,
  isSaveDisabled,
  onToggleLayer,
  onBeginEdit,
  onDraftNameChange,
  onCommitEdit,
  onCancelEdit,
  onSaveLayer,
  onUseLayerForModelling,
  onDeleteLayer,
}) => {
  const t = useTranslations('containers.map-sidebar-layers-panel');

  return (
    <li className="flex items-start justify-between">
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
                onChange={(event) => onDraftNameChange(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === 'Enter') onCommitEdit(slug);
                  if (event.key === 'Escape') onCancelEdit();
                }}
                onBlur={() => onCommitEdit(slug)}
                aria-label={t('edit-layer-name', { layer: layer.name })}
                className="w-full rounded-md border border-black bg-white px-2 py-1 text-sm focus:outline-none focus:ring-2 focus:ring-black/30"
              />
            </div>
          ) : (
            <Label htmlFor={`${layer.name}-switch`} className={switchLabelClassName}>
              <button
                type="button"
                className="hover:bg-gray-200 hover:text-gray-700 focus-visible:ring-black"
                onClick={() => onBeginEdit(slug, layer.name)}
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
