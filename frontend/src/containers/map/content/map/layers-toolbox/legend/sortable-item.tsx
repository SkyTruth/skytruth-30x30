import { CSS } from '@dnd-kit/utilities';
import { useSortable } from '@dnd-kit/sortable';
import { useAtomValue } from 'jotai';
import { Menu } from 'lucide-react';
import { useTranslations } from 'next-intl';

import { screenshotOpenAtom } from '@/containers/map/store';
import { cn } from '@/lib/classnames';
import { FCWithMessages } from '@/types';
import { LegendLegendComponent } from '@/types/generated/strapi.schemas';
import { LayerTyped, ParamsConfig } from '@/types/layers';

import LegendItem from './item';
import LegendItemHeader from './item-header';

type SortableLegendItemProps = {
  slug: string;
  title: string;
  isCustomLayer?: boolean;
  isVisible: boolean;
  opacity: number;
  color?: string;
  legend_config: LegendLegendComponent;
  params_config: ParamsConfig;
  onRemoveLayer: (slug: string) => void;
  onToggleLayerVisibility: (slug: string, isVisible: boolean) => void;
  onChangeLayerOpacity: (slug: string, opacity: number) => void;
  onChangeLayerColor?: (slug: string, color: string) => void;
};

const SortableLegendItem: FCWithMessages<SortableLegendItemProps> = ({
  slug,
  title,
  isCustomLayer,
  isVisible,
  opacity,
  color,
  legend_config,
  params_config,
  onRemoveLayer,
  onToggleLayerVisibility,
  onChangeLayerOpacity,
  onChangeLayerColor,
}) => {
  const t = useTranslations('containers.map');
  const screenshotOpen = useAtomValue(screenshotOpenAtom);

  const {
    attributes,
    listeners,
    setNodeRef,
    setActivatorNodeRef,
    transform,
    transition,
    isDragging,
  } = useSortable({ id: slug, data: { title } });

  const style = {
    transform: CSS.Translate.toString(transform),
    transition,
  };

  return (
    <div
      ref={setNodeRef}
      style={style}
      className={cn('relative flex items-start gap-x-2', {
        'opacity-50': isDragging,
      })}
    >
      {!screenshotOpen && (
        <button
          ref={setActivatorNodeRef}
          {...attributes}
          {...listeners}
          type="button"
          className="mt-[3px] shrink-0 touch-none cursor-grab rounded-sm text-gray-400 active:cursor-grabbing focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-black focus-visible:ring-offset-1"
          aria-label={t('drag-to-reorder-layer', { layer: title })}
        >
          <Menu className="h-4 w-4" aria-hidden />
        </button>
      )}
      <div className="min-w-0 flex-1">
        <LegendItemHeader
          slug={slug}
          title={title}
          isVisible={isVisible}
          opacity={opacity}
          isCustomLayer={isCustomLayer}
          color={color}
          onRemoveLayer={onRemoveLayer}
          onToggleLayerVisibility={onToggleLayerVisibility}
          onChangeLayerOpacity={onChangeLayerOpacity}
          onChangeLayerColor={onChangeLayerColor}
        />
        <div className="pt-1.5">
          <LegendItem
            config={legend_config as LayerTyped['legend_config']}
            paramsConfig={params_config as ParamsConfig}
          />
        </div>
      </div>
    </div>
  );
};

SortableLegendItem.messages = ['containers.map', ...LegendItemHeader.messages, ...LegendItem.messages];

export default SortableLegendItem;
