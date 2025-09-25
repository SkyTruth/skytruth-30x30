import { useMemo } from 'react';

import { useLocale, useTranslations } from 'next-intl';

import HorizontalBarChart from '@/components/charts/horizontal-bar-chart';
import Widget from '@/components/widget';
import { FISHING_PROTECTION_CHART_COLORS } from '@/constants/fishing-protection-chart-colors';
import { CUSTOM_REGION_CODE } from '@/containers/map/constants';
import { useSyncCustomRegion } from '@/containers/map/content/map/sync-settings';
import { FCWithMessages } from '@/types';
import { useGetAggregatedStats } from '@/types/generated/aggregated-stats';
import { useGetDataInfos } from '@/types/generated/data-info';
import type { AggregatedStats, AggregatedStatsEnvelope } from '@/types/generated/strapi.schemas';

type FishingProtectionWidgetProps = {
  location: string;
};

const FishingProtectionWidget: FCWithMessages<FishingProtectionWidgetProps> = ({ location }) => {
  const t = useTranslations('containers.map-sidebar-main-panel');
  const locale = useLocale();

  const [customRegionLocations] = useSyncCustomRegion();
  const locations =
    location === CUSTOM_REGION_CODE && customRegionLocations
      ? [...customRegionLocations].join(',')
      : location;

  const { data: fishingProtectionLevelsData, isFetching } = useGetAggregatedStats<
    AggregatedStats[]
  >(
    {
      locale,
      stats: 'fishing_protection_level',
      fishing_protection_level: 'highly',
      locations,
    },
    {
      query: {
        select: ({ data }) => data?.fishing_protection_level ?? [],
        placeholderData: { data: [] } as AggregatedStatsEnvelope,
        refetchOnWindowFocus: false,
      },
    }
  );

  const { data: metadata } = useGetDataInfos(
    {
      locale,
      filters: {
        slug: 'fishing-protection-level',
      },
      populate: 'data_sources',
    },
    {
      query: {
        select: ({ data }) =>
          data[0]
            ? {
                info: data[0]?.attributes?.content,
                sources: data[0]?.attributes?.data_sources?.data?.map(
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

  // Parse data to display in the chart
  const widgetChartData = useMemo(() => {
    if (!fishingProtectionLevelsData?.length) return [];
    const parsedProtectionLevel = (protectionLevel, stats) => {
      return {
        title: protectionLevel?.name,
        slug: protectionLevel.slug,
        background: FISHING_PROTECTION_CHART_COLORS[protectionLevel.slug],
        totalArea: stats.total_area,
        protectedArea: stats.protected_area,
        percentage: stats.coverage,
        info: metadata?.info,
        sources: metadata?.sources,
        updatedAt: stats.updatedAt,
      };
    };

    const parsedFishingProtectionLevelData = fishingProtectionLevelsData?.map((stats) => {
      const data = stats;
      const protectionLevel = data?.fishing_protection_level;

      return parsedProtectionLevel(protectionLevel, data);
    });

    return parsedFishingProtectionLevelData?.filter(Boolean) ?? [];
  }, [fishingProtectionLevelsData, metadata]);

  const noData = useMemo(() => {
    if (!widgetChartData.length) {
      return true;
    }

    const emptyValues = widgetChartData.every((d) => d.totalArea === Infinity);
    if (emptyValues) {
      return true;
    }

    return false;
  }, [widgetChartData]);

  return (
    <Widget
      title={t('level-of-fishing-protection')}
      lastUpdated={widgetChartData[0]?.updatedAt}
      noData={noData}
      loading={isFetching}
    >
      {widgetChartData.map((chartData) => (
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

FishingProtectionWidget.messages = [
  'containers.map-sidebar-main-panel',
  ...Widget.messages,
  ...HorizontalBarChart.messages,
];

export default FishingProtectionWidget;
