import { useMemo, memo } from 'react';

import { useLocale, useTranslations } from 'next-intl';

import HorizontalBarChart from '@/components/charts/horizontal-bar-chart';
import Widget from '@/components/widget';
import {
  MARINE_HABITAT_CHART_COLORS,
  TERRESTRIAL_HABITAT_CHART_COLORS,
} from '@/constants/habitat-chart-colors';
import { useSyncMapContentSettings } from '@/containers/map/sync-settings';
import { FCWithMessages } from '@/types';
import { CUSTOM_REGION_CODE } from '@/containers/map/constants';
import { useSyncCustomRegion } from '@/containers/map/content/map/sync-settings';
import { useGetAggregatedStats } from '@/types/generated/aggregated-stats';
import { useGetDataInfos } from '@/types/generated/data-info';
import type {
  LocationGroupsDataItemAttributes,
  AggregatedStatsEnvelope,
} from '@/types/generated/strapi.schemas';

type HabitatWidgetProps = {
  location: LocationGroupsDataItemAttributes;
};

const HabitatWidget: React.FC<HabitatWidgetProps> = ({ location }) => {
  const t = useTranslations('containers.map-sidebar-main-panel');
  const locale = useLocale();

  const [customRegionLocations] = useSyncCustomRegion();

  const locations =
    location.code === CUSTOM_REGION_CODE ? customRegionLocations.join(',') : location.code;

  const [{ tab }] = useSyncMapContentSettings();

  const [HABITAT_CHART_COLORS] = useMemo(() => {
    const total =
      tab === 'marine'
        ? Object.keys(MARINE_HABITAT_CHART_COLORS).length
        : Object.keys(TERRESTRIAL_HABITAT_CHART_COLORS).length;

    return [{ ...MARINE_HABITAT_CHART_COLORS, ...TERRESTRIAL_HABITAT_CHART_COLORS }, total];
  }, [tab]);

    const { data: habitatMetadatas } = useGetDataInfos<
    { slug: string; info: string; sources?: { id: number; title: string; url: string }[] }[]
  >(
    {
      locale,
      filters: {
        slug: Object.keys(HABITAT_CHART_COLORS),
      },
      // @ts-expect-error
      populate: {
        data_sources: {
          fields: ['title', 'url'],
        },
      },
      sort: 'updatedAt:desc',
    },
    {
      query: {
        select: ({ data }) =>
          data?.map((item) => ({
            slug: item.attributes.slug,
            info: item.attributes.content,
            sources: item.attributes.data_sources?.data?.map(
              ({ id, attributes: { title, url } }) => ({
                id,
                title,
                url,
              })
            ),
          })) ?? [],
      },
    }
  );

    const { data: chartData, isFetching } = useGetAggregatedStats<{
      title: string;
      slug: string;
      background: string;
      totalArea: number;
      protectedArea: number;
      info?: string;
      sources?: { id: number; title: string; url: string }[];
      updatedAt: string;
    }[]>(
      {
        locale,
        stats: 'habitat',
        environment: tab === 'marine' ? tab : 'terrestrial',
        locations,
      },
      {
      query: {
        select: ({ data: {habitat: habitatStats} }) => {
          if (!habitatStats?.length) {
            return [];
          }

          const parsedHabitats = new Set();
          // Reverse the array first because the endpoint returns data from oldest
          // to newest. This allows is to take only the newest recrods
          const reversedStats = [...habitatStats].reverse();

          const parsedData = reversedStats.reduce((parsed, entry) => {
            if (parsedHabitats.has(entry.habitat.slug)) {
              return parsed;
            }
            parsedHabitats.add(entry.habitat.slug);

            const stats = entry;
            let habitat = stats?.habitat;

            const metadata = habitatMetadatas?.find(({ slug }) => slug === habitat?.slug);

            parsed.push({
              title: habitat?.name,
              slug: habitat?.slug,
              background: HABITAT_CHART_COLORS[habitat?.slug],
              totalArea: stats.total_area,
              protectedArea: stats.protected_area,
              info: metadata?.info,
              sources: metadata?.sources,
              updatedAt: stats.updatedAt,
            });
            return parsed;
          }, []);

          return parsedData
            .sort((d1, d2) => {
              const keys = Object.keys(HABITAT_CHART_COLORS);
              return keys.indexOf(d1.slug) - keys.indexOf(d2.slug);
            })
            .filter(({ totalArea }) => totalArea !== 0);
        },
        placeholderData: {data: []} as AggregatedStatsEnvelope,
        refetchOnWindowFocus: false,
      }
    }
  );

  const { data: metadata } = useGetDataInfos(
    {
      locale,
      filters: {
        slug: `habitat-widget-${tab}`,
      },
      populate: 'data_sources',
    },
    {
      query: {
        select: ({ data }) =>
          data[0]
            ? {
                info: data[0].attributes.content,
                sources: data[0].attributes?.data_sources?.data?.map(
                  ({ id, attributes: { title, url } }) => ({
                    id,
                    title,
                    url,
                  })
                ),
              }
            : undefined,
      },
    }
  );

  return (
    <Widget
      title={t('proportion-habitat-within-protected-areas')}
      lastUpdated={chartData[chartData.length - 1]?.updatedAt}
      noData={!chartData.length}
      loading={isFetching}
      info={metadata?.info}
      sources={metadata?.sources}
    >
      {chartData.map((chartData) => (
        <HorizontalBarChart
          key={chartData.slug}
          className="py-2"
          data={chartData}
          showTarget={false}
        />
      ))}
    </Widget>
  );
};

type Messages = Parameters<typeof useTranslations>[0][];
type MemoizedWidgetType = React.FC<HabitatWidgetProps> & { messages: Messages };

const MemoizedWidget = memo(HabitatWidget) as unknown as MemoizedWidgetType;

MemoizedWidget.messages = [
  'containers.map-sidebar-main-panel',
  ...Widget.messages,
  ...HorizontalBarChart.messages,
];

export default MemoizedWidget;
