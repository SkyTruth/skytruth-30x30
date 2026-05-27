import { useCallback, useMemo, useRef, useState } from 'react';
import {
  DndContext,
  DragEndEvent,
  PointerSensor,
  closestCenter,
  useSensor,
  useSensors,
} from '@dnd-kit/core';
import { restrictToParentElement, restrictToVerticalAxis } from '@dnd-kit/modifiers';
import { SortableContext, arrayMove, verticalListSortingStrategy } from '@dnd-kit/sortable';
import { useAtom } from 'jotai';
import { useLocale, useTranslations } from 'next-intl';

import {
  useSyncMapLayerSettings,
  useSyncMapLayers,
} from '@/containers/map/content/map/sync-settings';
import { allActiveLayersAtom, customLayersAtom } from '@/containers/map/store';
import { FCWithMessages } from '@/types';
import { useGetLayers } from '@/types/generated/layer';
import { Layer, LegendLegendComponent } from '@/types/generated/strapi.schemas';
import { LayerTyped, ParamsConfig } from '@/types/layers';

import SortableLegendItem from './sortable-item';

const Legend: FCWithMessages = () => {
  const t = useTranslations('containers.map');
  const locale = useLocale();

  const [activeLayers, setPredefinedMapLayers] = useSyncMapLayers();
  const [layerSettings, setLayerSettings] = useSyncMapLayerSettings();

  const [customLayers, setCustomLayers] = useAtom(customLayersAtom);
  const [allActiveLayers, setAllActiveLayers] = useAtom(allActiveLayersAtom);

  const legendContainerRef = useRef<HTMLDivElement>(null);

  const [announcement, setAnnouncement] = useState('');
  const layersQuery = useGetLayers<Layer[]>(
    {
      locale,
      sort: 'title:asc',
      // @ts-ignore
      fields: ['title', 'params_config', 'slug'],

      // @ts-ignore
      populate: {
        legend_config: {
          populate: {
            items: true,
          },
        },
        environment: {
          fields: ['slug'],
        },
      },
    },
    {
      query: {
        select: ({ data }) =>
          data
            .filter((item) => activeLayers.includes(item.slug))
            .sort((a, b) => {
              const indexA = activeLayers.indexOf(a.slug);
              const indexB = activeLayers.indexOf(b.slug);
              return indexA - indexB;
            }),
        placeholderData: { data: [] },
        queryKey: ['layers', locale, activeLayers],
        keepPreviousData: true,
      },
    }
  );

  const onRemoveLayer = useCallback(
    (layerSlug: string) => {
      if (!customLayers[layerSlug]) {
        setPredefinedMapLayers((currentLayers) => {
          return currentLayers.filter((slug) => slug !== layerSlug);
        });
      } else {
        const updatedCustomLayers = { ...customLayers };
        updatedCustomLayers[layerSlug].isActive = false;
        setCustomLayers(updatedCustomLayers);
      }
    },
    [customLayers, setCustomLayers, setPredefinedMapLayers]
  );

  const onToggleLayerVisibility = useCallback(
    (layerSlug: string, isVisible: boolean) => {
      if (!customLayers[layerSlug]) {
        setLayerSettings((prev) => ({
          ...prev,
          [layerSlug]: {
            ...prev[layerSlug],
            visibility: isVisible,
          },
        }));
      } else {
        const updatedCustomLayers = { ...customLayers };
        updatedCustomLayers[layerSlug].isVisible = !updatedCustomLayers[layerSlug].isVisible;
        setCustomLayers(updatedCustomLayers);
      }
    },
    [customLayers, setCustomLayers, setLayerSettings]
  );

  const onChangeLayerOpacity = useCallback(
    (layerSlug: string, opacity: number) => {
      if (!customLayers[layerSlug]) {
        setLayerSettings((prev) => ({
          ...prev,
          [layerSlug]: {
            ...prev[layerSlug],
            opacity,
          },
        }));
        return;
      }

      setCustomLayers((prev) => ({
        ...prev,
        ...(prev[layerSlug]
          ? {
              [layerSlug]: {
                ...prev[layerSlug],
                style: {
                  ...prev[layerSlug].style,
                  opacity,
                },
              },
            }
          : {}),
      }));
    },
    [customLayers, setCustomLayers, setLayerSettings]
  );

  const onChangeLayerColor = useCallback(
    (layerSlug: string, color: string) => {
      setCustomLayers((prev) => ({
        ...prev,
        ...(prev[layerSlug]
          ? {
              [layerSlug]: {
                ...prev[layerSlug],
                style: {
                  ...prev[layerSlug].style,
                  fillColor: color,
                  lineColor: color,
                },
              },
            }
          : {}),
      }));
    },
    [setCustomLayers]
  );

  const sensors = useSensors(
    useSensor(PointerSensor, {
      activationConstraint: { distance: 5 },
    })
  );
  const getLayerLabel = useCallback(
    (slug: string) =>
      customLayers[slug]?.name ??
      layersQuery.data?.find((layer) => layer.slug === slug)?.title ??
      slug,
    [customLayers, layersQuery.data]
  );
  const findScrollContainer = useCallback((): HTMLElement | null => {
    let el = legendContainerRef.current?.parentElement ?? null;
    while (el) {
      const { overflowY } = window.getComputedStyle(el);
      if (overflowY === 'auto' || overflowY === 'scroll') return el;
      el = el.parentElement;
    }
    return null;
  }, []);

  const reorderLayer = useCallback(
    (slug: string, toIndex: number) => {
      const fromIndex = allActiveLayers.indexOf(slug);
      if (
        fromIndex === -1 ||
        toIndex < 0 ||
        toIndex >= allActiveLayers.length ||
        toIndex === fromIndex
      ) {
        return false;
      }
      const neighborLabel = getLayerLabel(allActiveLayers[toIndex]);
      const direction = toIndex > fromIndex ? 'below' : 'above';
      const reordered = arrayMove(allActiveLayers, fromIndex, toIndex);
      setAllActiveLayers(reordered);
      setPredefinedMapLayers(reordered.filter((layerSlug) => !customLayers[layerSlug]));
      setAnnouncement(`${getLayerLabel(slug)} moved ${direction} ${neighborLabel}`);
      return true;
    },
    [allActiveLayers, customLayers, getLayerLabel, setAllActiveLayers, setPredefinedMapLayers]
  );

  const onDragEnd = useCallback(
    ({ active, over }: DragEndEvent) => {
      if (!over || active.id === over.id) return;
      const scrollContainer = findScrollContainer();
      const savedScrollTop = scrollContainer?.scrollTop ?? 0;
      reorderLayer(active.id as string, allActiveLayers.indexOf(over.id as string));
      requestAnimationFrame(() => {
        if (scrollContainer) scrollContainer.scrollTop = savedScrollTop;
      });
    },
    [allActiveLayers, findScrollContainer, reorderLayer]
  );

  const moveLayer = useCallback(
    (slug: string, direction: 'up' | 'down') => {
      const fromIndex = allActiveLayers.indexOf(slug);
      if (fromIndex === -1) return;
      const moved = reorderLayer(slug, fromIndex + (direction === 'up' ? -1 : 1));
      if (moved) {
        requestAnimationFrame(() => {
          document
            .querySelector(`[data-layer-slug="${slug}"]`)
            ?.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
        });
      }
    },
    [allActiveLayers, reorderLayer]
  );

  const legendItems = useMemo(() => {
    if (!layersQuery.data?.length) {
      return null;
    }

    return allActiveLayers.map((slug) => {
      let opacity = 1;
      let color: string | undefined;
      let isVisible = true;
      let isCustomLayer = false;
      let title: string;
      let legend_config: LegendLegendComponent;
      let params_config;

      if (!customLayers[slug] && layersQuery.data?.length) {
        const layer = layersQuery.data.filter((layer) => layer.slug === slug)[0];

        if (!layer) return null;

        legend_config = layer.legend_config;
        params_config = layer.params_config;

        title = layer.title;
        isVisible = layerSettings[slug]?.visibility !== false;
        opacity = layerSettings[slug]?.opacity ?? 1;
        
      } else {
        const layer = customLayers[slug];

        isCustomLayer = true;
        title = layer.name;
        isVisible = layer.isVisible;
        opacity = layer.style.opacity ?? 0.5;
        color = layer.style.fillColor ?? layer.style.lineColor;
        legend_config = {
          type: 'icon',
          items: [
            {
              color: layer.style.fillColor,
              description: null,
              icon: 'circle-with-fill',
              value: title,
            },
          ],
        };

        params_config = [
          {
            key: 'opacity',
            default: opacity,
          },
        ];
      }

      return (
        <SortableLegendItem
          key={slug}
          slug={slug}
          title={title}
          isCustomLayer={isCustomLayer}
          isVisible={isVisible}
          opacity={opacity}
          color={color}
          legend_config={legend_config as LayerTyped['legend_config']}
          params_config={params_config as ParamsConfig}
          onRemoveLayer={onRemoveLayer}
          onToggleLayerVisibility={onToggleLayerVisibility}
          onChangeLayerOpacity={onChangeLayerOpacity}
          onChangeLayerColor={onChangeLayerColor}
          onMoveLayer={moveLayer}
        />
      );
    });
  }, [
    allActiveLayers,
    customLayers,
    layerSettings,
    layersQuery.data,
    moveLayer,
    onChangeLayerOpacity,
    onChangeLayerColor,
    onRemoveLayer,
    onToggleLayerVisibility,
  ]);

  return (
    <div ref={legendContainerRef} className="pl-2 pr-4 py-2 select-none">
      {!layersQuery.data?.length && (
        <p>
          {t.rich('open-layers-to-add-to-map', {
            b: (chunks) => <span className="text-sm font-black uppercase">{chunks}</span>,
          })}
        </p>
      )}
      <div role="status" aria-live="assertive" aria-atomic="true" className="sr-only">
        {announcement}
      </div>
      <DndContext
        sensors={sensors}
        collisionDetection={(args) => {
          if (!args.pointerCoordinates) return closestCenter(args);
          const { x, y } = args.pointerCoordinates;
          return closestCenter({
            ...args,
            collisionRect: { top: y, bottom: y, left: x, right: x, width: 0, height: 0 },
          });
        }}
        onDragEnd={onDragEnd}
        modifiers={[restrictToVerticalAxis, restrictToParentElement]}
        accessibility={{
          announcements: {
            onDragStart: () => undefined,
            onDragOver: () => undefined,
            onDragEnd: () => undefined,
            onDragCancel: () => undefined,
          },
        }}
      >
        <SortableContext items={allActiveLayers} strategy={verticalListSortingStrategy}>
          <div className="flex flex-col gap-y-5">{legendItems}</div>
        </SortableContext>
      </DndContext>
    </div>
  );
};

Legend.messages = ['containers.map', ...SortableLegendItem.messages];

export default Legend;
