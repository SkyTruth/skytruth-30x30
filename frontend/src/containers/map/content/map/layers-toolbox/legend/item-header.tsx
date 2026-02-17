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
  '#e61919',
  '#e68f19',
  '#c8e619',
  '#52e619',
  '#19e68f',
  '#19e6e6',
  '#1970e6',
  '#5219e6',
  '#c819e6',
  '#e6198f',
];

type LegendItemHeaderProps = {
  fillColor?: string;
  isCustomLayer?: boolean;
  isFirst: boolean;
  isLast: boolean;
  isVisible: boolean;
  lineColor?: string;
  onChangeLayerFillColor?: (slug: string, color: string) => void;
  onChangeLayerLineColor?: (slug: string, color: string) => void;
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
  fillColor,
  isCustomLayer = false,
  isFirst,
  isLast,
  isVisible,
  lineColor,
  onChangeLayerFillColor,
  onChangeLayerLineColor,
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
  const styleButtonLabel = isCustomLayer ? t('change-layer-style') : t('change-opacity');

  return (
    <div className="flex items-center justify-between gap-4">
      <TooltipProvider>
        <Tooltip>
          <TooltipTrigger asChild>
            <div className="overflow-hidden text-ellipsis whitespace-nowrap font-mono text-xs font-bold ring-offset-white transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-black focus-visible:ring-offset-2 [&_svg]:aria-[expanded=true]:rotate-180">
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
                onClick={() => onMoveLayerUp(slug)}
              >
                <span className="sr-only">{t('move-up')}</span>
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
                onClick={() => onMoveLayerDown(slug)}
              >
                <span className="sr-only">{t('move-down')}</span>
                <Icon icon={ArrowDownIcon} className="h-3 w-3" />
              </Button>
            </TooltipTrigger>
            <TooltipContent>{t('move-down')}</TooltipContent>
          </Tooltip>
          <Tooltip>
            <Popover>
              <TooltipTrigger asChild>
                <PopoverTrigger asChild>
                  <Button type="button" variant="ghost" size="icon-sm">
                    <span className="sr-only">{styleButtonLabel}</span>
                    <Icon icon={OpacityIcon} className="h-3.5 w-3.5" />
                  </Button>
                </PopoverTrigger>
              </TooltipTrigger>
              <TooltipContent>{styleButtonLabel}</TooltipContent>
              <PopoverContent className="w-56 space-y-3" align="end">
                <div>
                  <Label className="mb-2 block text-xs">{t('opacity')}</Label>
                  <Slider
                    thumbLabel={t('opacity')}
                    value={[opacity]}
                    max={1}
                    step={0.1}
                    onValueChange={([value]) => onChangeLayerOpacity(slug, value)}
                  />
                </div>
                {isCustomLayer && (
                  <>
                    <div>
                      <Label className="mb-2 block text-xs">{t('fill-color')}</Label>
                      <div
                        role="radiogroup"
                        aria-label={t('fill-color')}
                        className="grid grid-cols-5 gap-2"
                      >
                        {LAYER_STYLE_COLORS.map((color) => (
                          <button
                            key={`fill-${color}`}
                            type="button"
                            role="radio"
                            aria-checked={fillColor === color}
                            aria-label={t('color-option', { color })}
                            className={cn(
                              'h-5 w-5 rounded-full border border-black',
                              'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-black focus-visible:ring-offset-1',
                              {
                                'ring-2 ring-black ring-offset-1': fillColor === color,
                              }
                            )}
                            style={{ backgroundColor: color }}
                            onClick={() => onChangeLayerFillColor?.(slug, color)}
                          />
                        ))}
                      </div>
                    </div>
                    <div>
                      <Label className="mb-2 block text-xs">{t('line-color')}</Label>
                      <div
                        role="radiogroup"
                        aria-label={t('line-color')}
                        className="grid grid-cols-5 gap-2"
                      >
                        {LAYER_STYLE_COLORS.map((color) => (
                          <button
                            key={`line-${color}`}
                            type="button"
                            role="radio"
                            aria-checked={lineColor === color}
                            aria-label={t('color-option', { color })}
                            className={cn(
                              'h-5 w-5 rounded-full border border-black',
                              'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-black focus-visible:ring-offset-1',
                              {
                                'ring-2 ring-black ring-offset-1': lineColor === color,
                              }
                            )}
                            style={{ backgroundColor: color }}
                            onClick={() => onChangeLayerLineColor?.(slug, color)}
                          />
                        ))}
                      </div>
                    </div>
                  </>
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
                onClick={() => onToggleLayerVisibility(slug, !isVisible)}
              >
                <span className="sr-only">{isVisible ? t('hide') : t('show')}</span>
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
                onClick={() => {
                  onRemoveLayer(slug);
                }}
              >
                <span className="sr-only">{t('remove')}</span>
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
