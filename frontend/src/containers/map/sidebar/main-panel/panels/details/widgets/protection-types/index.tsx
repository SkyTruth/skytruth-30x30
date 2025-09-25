import { useMemo } from 'react';

import { useLocale, useTranslations } from 'next-intl';

import HorizontalBarChart from '@/components/charts/horizontal-bar-chart';
import Widget from '@/components/widget';
import { PROTECTION_TYPES_CHART_COLORS } from '@/constants/protection-types-chart-colors';
import { CUSTOM_REGION_CODE } from '@/containers/map/constants';
import { useSyncCustomRegion } from '@/containers/map/content/map/sync-settings';
import { FCWithMessages } from '@/types';
import { useGetAggregatedStats } from '@/types/generated/aggregated-stats';
import { useGetDataInfos } from '@/types/generated/data-info';
import type { AggregatedStats, AggregatedStatsEnvelope } from '@/types/generated/strapi.schemas';

import MissingCountriesList from '../missing-countries-list.tsx';

type ProtectionTypesWidgetProps = {
  location: string;
};

const ProtectionTypesWidget: FCWithMessages<ProtectionTypesWidgetProps> = ({ location }) => {
  const t = useTranslations('containers.map-sidebar-main-panel');
  const locale = useLocale();

  const [customRegionLocations] = useSyncCustomRegion();

  const locations =
    location === CUSTOM_REGION_CODE && customRegionLocations
      ? [...customRegionLocations].join(',')
      : location;

  const { data: protectionLevelData, isFetching } = useGetAggregatedStats<AggregatedStats[]>(
    {
      locale,
      stats: 'mpaa_protection_level',
      mpaa_protection_level: 'fully-highly-protected',
      locations,
    },
    {
      query: {
        select: ({ data }) => data?.mpaa_protection_level ?? [],
        placeholderData: { data: [] } as AggregatedStatsEnvelope,
        refetchOnWindowFocus: false,
      },
    }
  );

  const { data: metadata } = useGetDataInfos(
    {
      locale,
      filters: {
        slug: 'fully-highly-protected',
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

  const missingLocations = useMemo(() => {
    const allLocations = new Set(locations.split(','));
    const includedLocaitons = new Set(protectionLevelData[0]?.locations);

    return [...allLocations.difference(includedLocaitons)];
  }, [locations, protectionLevelData]);

  // Go through all the relevant stats, find the last updated one's value
  const lastUpdated = useMemo(() => {
    const updatedAtValues = protectionLevelData?.reduce(
      (acc, curr) => [...acc, curr?.updatedAt],
      []
    );

    return updatedAtValues?.sort()?.reverse()?.[0];
  }, [protectionLevelData]);

  // Parse data to display in the chart
  const widgetChartData = useMemo(() => {
    if (!protectionLevelData.length) return [];

    const parseProtectionLevelStats = (protectionLevelStats) => {
      const mpaaProtectionLevel = protectionLevelStats?.mpaa_protection_level;
      const totalArea = protectionLevelStats?.total_area;

      const barColor = PROTECTION_TYPES_CHART_COLORS[mpaaProtectionLevel.slug];

      return {
        title: mpaaProtectionLevel?.name,
        slug: mpaaProtectionLevel?.slug,
        background: barColor,
        totalArea: Number(totalArea),
        protectedArea: protectionLevelStats?.protected_area,
        percentage: protectionLevelStats?.coverage,
        info: metadata?.info,
        sources: metadata?.sources,
      };
    };

    return protectionLevelData?.map((stats) => parseProtectionLevelStats(stats));
  }, [metadata, protectionLevelData]);

  const noData = !widgetChartData.length;
  const loading = isFetching;

  return (
    <Widget
      title={t('marine-conservation-protection-levels')}
      lastUpdated={lastUpdated}
      noData={noData}
      noDataMessage={t('not-assessed')}
      loading={loading}
    >
      {widgetChartData.map((chartData) => (
        <HorizontalBarChart
          key={chartData.slug}
          showTarget={location === 'GLOB'}
          className="py-2"
          data={chartData}
        />
      ))}
      <MissingCountriesList countries={missingLocations} />
    </Widget>
  );
};

ProtectionTypesWidget.messages = [
  'containers.map-sidebar-main-panel',
  ...Widget.messages,
  ...HorizontalBarChart.messages,
];

export default ProtectionTypesWidget;
