import { useId } from 'react';

import { useTranslations } from 'next-intl';
import { HiEye, HiEyeOff } from 'react-icons/hi';

import { Button } from '@/components/ui/button';
import Icon from '@/components/ui/icon';
import { Label } from '@/components/ui/label';
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover';
import { Slider } from '@/components/ui/slider';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip';
import { cn } from '@/lib/classnames';
import ArrowDownIcon from '@/styles/icons/arrow-down.svg';
import ArrowTopIcon from '@/styles/icons/arrow-top.svg';
import CloseIcon from '@/styles/icons/close.svg';
import OpacityIcon from '@/styles/icons/opacity.svg';
import { FCWithMessages } from '@/types';

const LAYER_STYLE_COLORS = [
  { value: '#86a6f0', nameKey: 'soft-blue' },
  { value: '#a9db93', nameKey: 'soft-green' },
  { value: '#dde44f', nameKey: 'soft-lime' },
  { value: '#d55d55', nameKey: 'muted-red' },
  { value: '#c95aa8', nameKey: 'muted-pink' },
] as const;

type LegendItemHeaderProps = {
  color?: string;
  isCustomLayer?: boolean;
  isFirst: boolean;
  isLast: boolean;
  isVisible: boolean;
  onChangeLayerColor?: (slug: string, color: string) => void;
  onChangeLayerOpacity: (slug: string, opacity: number) => void;
  onMoveLayerDown: (slug: string) => void;
  onMoveLayerUp: (slug: string) => void;
  opacity: number;
  onRemoveLayer: (slug: string) => void;
  onToggleLayerVisibility: (slug: string, isVisible: boolean) => void;
  slug: string;
  title: string;
};

const LegendItemHeader: FCWithMessages<LegendItemHeaderProps> = ({
  color,
  isCustomLayer = false,
  isFirst,
  isLast,
  isVisible,
  onChangeLayerColor,
  onChangeLayerOpacity,
  onMoveLayerDown,
  onMoveLayerUp,
  opacity,
  onRemoveLayer,
  onToggleLayerVisibility,
  slug,
  title,
}) => {
  const t = useTranslations('containers.map');
  const layerTitleId = useId();
  const styleButtonLabel = isCustomLayer ? t('change-layer-style') : t('change-opacity');
  const moveUpLabel = t('move-up-layer', { layer: title });
  const moveDownLabel = t('move-down-layer', { layer: title });
  const styleButtonLayerLabel = isCustomLayer
    ? t('change-layer-style-layer', { layer: title })
    : t('change-opacity-layer', { layer: title });
  const toggleVisibilityLabel = isVisible
    ? t('hide-layer', { layer: title })
    : t('show-layer', { layer: title });
  const removeLabel = t('remove-layer', { layer: title });
  const opacityThumbLabel = t('opacity-layer', { layer: title });
  const colorGroupLabel = t('color-layer', { layer: title });

  return (
    <div
      className="flex items-center justify-between gap-4"
      role="group"
      aria-labelledby={layerTitleId}
    >
      <TooltipProvider>
        <Tooltip>
          <TooltipTrigger asChild>
            <div
              id={layerTitleId}
              className="overflow-hidden text-ellipsis whitespace-nowrap font-mono text-xs font-bold ring-offset-white transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-black focus-visible:ring-offset-2 [&_svg]:aria-[expanded=true]:rotate-180"
            >
              {title}
            </div>
          </TooltipTrigger>
          <TooltipContent>{title}</TooltipContent>
        </Tooltip>
      </TooltipProvider>
      <TooltipProvider>
        <div className="flex shrink-0 items-center">
          <Tooltip delayDuration={0}>
            <TooltipTrigger asChild>
              <Button
                type="button"
                variant="ghost"
                size="icon-sm"
                disabled={isFirst}
                aria-label={moveUpLabel}
                onClick={() => onMoveLayerUp(slug)}
              >
                <span className="sr-only">{moveUpLabel}</span>
                <Icon icon={ArrowTopIcon} className="h-3 w-3" />
              </Button>
            </TooltipTrigger>
            <TooltipContent>{t('move-up')}</TooltipContent>
          </Tooltip>
          <Tooltip>
            <TooltipTrigger asChild>
              <Button
                type="button"
                variant="ghost"
                size="icon-sm"
                disabled={isLast}
                aria-label={moveDownLabel}
                onClick={() => onMoveLayerDown(slug)}
              >
                <span className="sr-only">{moveDownLabel}</span>
                <Icon icon={ArrowDownIcon} className="h-3 w-3" />
              </Button>
            </TooltipTrigger>
            <TooltipContent>{t('move-down')}</TooltipContent>
          </Tooltip>
          <Tooltip>
            <Popover>
              <TooltipTrigger asChild>
                <PopoverTrigger asChild>
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon-sm"
                    aria-label={styleButtonLayerLabel}
                  >
                    <span className="sr-only">{styleButtonLayerLabel}</span>
                    <Icon icon={OpacityIcon} className="h-3.5 w-3.5" />
                  </Button>
                </PopoverTrigger>
              </TooltipTrigger>
              <TooltipContent>{styleButtonLabel}</TooltipContent>
              <PopoverContent className="w-56 space-y-3" align="end">
                <div>
                  <Label className="mb-2 block text-xs">{t('opacity')}</Label>
                  <Slider
                    thumbLabel={opacityThumbLabel}
                    value={[opacity]}
                    max={1}
                    step={0.1}
                    onValueChange={([value]) => onChangeLayerOpacity(slug, value)}
                  />
                </div>
                {isCustomLayer && (
                  <div>
                    <Label className="mb-2 block text-xs">{t('color')}</Label>
                    <div
                      role="radiogroup"
                      aria-label={colorGroupLabel}
                      className="grid grid-cols-5 gap-2"
                    >
                      {LAYER_STYLE_COLORS.map(({ value, nameKey }) => (
                        <button
                          key={`color-${value}`}
                          type="button"
                          role="radio"
                          aria-checked={color === value}
                          aria-label={t('change-color', {
                            layer: title,
                            color: t(`layer-style-color-options.${nameKey}`),
                          })}
                          className={cn(
                            'h-5 w-5 rounded-full border border-black',
                            'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-black focus-visible:ring-offset-1',
                            {
                              'ring-2 ring-black ring-offset-1': color === value,
                            }
                          )}
                          style={{ backgroundColor: value }}
                          onClick={() => onChangeLayerColor?.(slug, value)}
                        />
                      ))}
                    </div>
                  </div>
                )}
              </PopoverContent>
            </Popover>
          </Tooltip>
          <Tooltip>
            <TooltipTrigger asChild>
              <Button
                type="button"
                variant="ghost"
                size="icon-sm"
                aria-label={toggleVisibilityLabel}
                onClick={() => onToggleLayerVisibility(slug, !isVisible)}
              >
                <span className="sr-only">{toggleVisibilityLabel}</span>
                {isVisible && <HiEye className="h-4 w-4" aria-hidden />}
                {!isVisible && <HiEyeOff className="h-4 w-4" aria-hidden />}
              </Button>
            </TooltipTrigger>
            <TooltipContent>{isVisible ? t('hide') : t('show')}</TooltipContent>
          </Tooltip>
          <Tooltip>
            <TooltipTrigger asChild>
              <Button
                type="button"
                variant="ghost"
                size="icon-sm"
                aria-label={removeLabel}
                onClick={() => {
                  onRemoveLayer(slug);
                }}
              >
                <span className="sr-only">{removeLabel}</span>
                <Icon icon={CloseIcon} className="h-3 w-3" />
              </Button>
            </TooltipTrigger>
            <TooltipContent>{t('remove')}</TooltipContent>
          </Tooltip>
        </div>
      </TooltipProvider>
    </div>
  );
};

LegendItemHeader.messages = ['containers.map'];

export default LegendItemHeader;
