import { type KeyboardEvent } from 'react';

import { useSortable } from '@dnd-kit/sortable';
import { CSS } from '@dnd-kit/utilities';

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
  onDragHandleFocus: () => void;
  onMoveLayer: (slug: string, direction: 'up' | 'down') => void;
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
  onDragHandleFocus,
  onMoveLayer,
}) => {
  const { listeners, setNodeRef, setActivatorNodeRef, transform, transition, isDragging } =
    useSortable({ id: slug, data: { title } });
  const style = {
    transform: CSS.Translate.toString(transform),
    transition,
  };

  const handleKeyDown = (event: KeyboardEvent<HTMLButtonElement>) => {
    if (event.altKey && event.key === 'ArrowUp') {
      event.preventDefault();
      onMoveLayer(slug, 'up');
    } else if (event.altKey && event.key === 'ArrowDown') {
      event.preventDefault();
      onMoveLayer(slug, 'down');
    }
  };

  return (
    <div
      ref={setNodeRef}
      style={style}
      data-layer-slug={slug}
      className={cn('relative', {
        'opacity-50': isDragging,
      })}
    >
      <LegendItemHeader
        slug={slug}
        title={title}
        isVisible={isVisible}
        opacity={opacity}
        isCustomLayer={isCustomLayer}
        color={color}
        dragHandleRef={setActivatorNodeRef}
        dragListeners={listeners}
        onDragHandleFocus={onDragHandleFocus}
        onDragKeyDown={handleKeyDown}
        onRemoveLayer={onRemoveLayer}
        onToggleLayerVisibility={onToggleLayerVisibility}
        onChangeLayerOpacity={onChangeLayerOpacity}
        onChangeLayerColor={onChangeLayerColor}
      />
      <div className="pl-5 pt-1.5">
        <LegendItem
          config={legend_config as LayerTyped['legend_config']}
          paramsConfig={params_config as ParamsConfig}
        />
      </div>
    </div>
  );
};

SortableLegendItem.messages = [
  'containers.map',
  ...LegendItemHeader.messages,
  ...LegendItem.messages,
];
export default SortableLegendItem;
