import { useMemo } from 'react';

import { useLocale, useTranslations } from 'next-intl';

import HorizontalBarChart from '@/components/charts/horizontal-bar-chart';
import Widget from '@/components/widget';
import { PROTECTION_TYPES_CHART_COLORS } from '@/constants/protection-types-chart-colors';
import { FCWithMessages } from '@/types';
import { useGetDataInfos } from '@/types/generated/data-info';
import { useGetMpaaProtectionLevelStats } from '@/types/generated/mpaa-protection-level-stat';
import type { LocationGroupsDataItemAttributes } from '@/types/generated/strapi.schemas';

type ProtectionTypesWidgetProps = {
  location: LocationGroupsDataItemAttributes;
};

const ProtectionTypesWidget: FCWithMessages<ProtectionTypesWidgetProps> = ({ location }) => {
  const t = useTranslations('containers.map-sidebar-main-panel');
  const locale = useLocale();

  // Get protection levels data for the location
  const {
    data: { data: protectionLevelsStatsData },
    isFetching: isFetchingProtectionLevelsStatsData,
  } = useGetMpaaProtectionLevelStats(
    {
      locale,
      filters: {
        location: {
          code: location?.code || 'GLOB',
        },
      },
      populate: '*',
      'pagination[limit]': -1,
    },
    {
      query: {
        enabled: Boolean(location?.code),
        select: ({ data }) => ({ data }),
        placeholderData: { data: [] },
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

  // Go through all the relevant stats, find the last updated one's value
  const lastUpdated = useMemo(() => {
    const updatedAtValues = protectionLevelsStatsData?.reduce(
      (acc, curr) => [...acc, curr?.attributes?.updatedAt],
      []
    );

    return updatedAtValues?.sort()?.reverse()?.[0];
  }, [protectionLevelsStatsData]);

  // Parse data to display in the chart
  const widgetChartData = useMemo(() => {
    if (!protectionLevelsStatsData.length) return [];

    const parseProtectionLevelStats = (protectionLevelStats) => {
      const mpaaProtectionLevel = protectionLevelStats?.mpaa_protection_level?.data?.attributes;
      const location = protectionLevelStats?.location?.data?.attributes;

      const barColor = PROTECTION_TYPES_CHART_COLORS[mpaaProtectionLevel?.slug];

      return {
        title: mpaaProtectionLevel?.name,
        slug: mpaaProtectionLevel?.slug,
        background: barColor,
        totalArea: Number(location?.total_marine_area),
        protectedArea: protectionLevelStats?.area,
        percentage: protectionLevelStats?.percentage,
        info: metadata?.info,
        sources: metadata?.sources,
      };
    };

    return protectionLevelsStatsData?.map(({ attributes }) =>
      parseProtectionLevelStats(attributes)
    );
  }, [metadata, protectionLevelsStatsData]);

  const noData = !widgetChartData.length;
  const loading = isFetchingProtectionLevelsStatsData;
  console.log(widgetChartData)

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
          showTarget={location?.code === 'GLOB'}
          className="py-2"
          data={chartData}
        />
      ))}
    </Widget>
  );
};

ProtectionTypesWidget.messages = [
  'containers.map-sidebar-main-panel',
  ...Widget.messages,
  ...HorizontalBarChart.messages,
];

export default ProtectionTypesWidget;
