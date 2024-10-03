import { useMemo } from 'react';

import { useLocale, useTranslations } from 'next-intl';

import HorizontalBarChart from '@/components/charts/horizontal-bar-chart';
import Widget from '@/components/widget';
import { FISHING_PROTECTION_CHART_COLORS } from '@/constants/fishing-protection-chart-colors';
import { FCWithMessages } from '@/types';
import { useGetDataInfos } from '@/types/generated/data-info';
import { useGetLocations } from '@/types/generated/location';
import type { LocationGroupsDataItemAttributes } from '@/types/generated/strapi.schemas';

type FishingProtectionWidgetProps = {
  location: LocationGroupsDataItemAttributes;
};

const FishingProtectionWidget: FCWithMessages<FishingProtectionWidgetProps> = ({ location }) => {
  const t = useTranslations('containers.map-sidebar-main-panel');
  const locale = useLocale();

  // Get protection levels data for the location
  const {
    data: { data: protectionLevelsData },
    isFetching: isFetchingProtectionLevelsData,
  } = useGetLocations(
    {
      filters: {
        code: location?.code,
      },
      // eslint-disable-next-line @typescript-eslint/ban-ts-comment
      // @ts-ignore
      populate: {
        fishing_protection_level_stats: {
          filters: {
            fishing_protection_level: {
              slug: 'highly',
            },
          },
          populate: {
            fishing_protection_level: '*',
          },
        },
      },
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
                  ({ attributes: { title, url } }) => ({
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
    if (!protectionLevelsData.length) return [];

    const parsedProtectionLevel = (label: string, protectionLevel, stats) => {
      const totalAreaPercentage = (stats?.area / stats?.pct) * 100;

      // There are circumstances in which pct is 0, which will cause the percentage calculation to be NaN.
      // This is a safeguard so that if the data is unexpected, we don't display NaN on the screen.
      if (isNaN(totalAreaPercentage)) return null;

      return {
        title: label,
        slug: protectionLevel.slug,
        background: FISHING_PROTECTION_CHART_COLORS[protectionLevel.slug],
        totalArea: totalAreaPercentage,
        protectedArea: stats?.area,
        info: metadata?.info,
        sources: metadata?.sources,
      };
    };

    const fishingProtectionLevelStats =
      protectionLevelsData[0]?.attributes?.fishing_protection_level_stats.data;

    const parsedFishingProtectionLevelData = fishingProtectionLevelStats?.map((stats) => {
      const data = stats?.attributes;
      const protectionLevel = data?.fishing_protection_level?.data.attributes;
      return parsedProtectionLevel(t('highly-protected-from-fishing'), protectionLevel, data);
    });

    return parsedFishingProtectionLevelData?.filter(Boolean) ?? [];
  }, [t, protectionLevelsData, metadata]);

  const noData = !widgetChartData.length;
  const loading = isFetchingProtectionLevelsData;

  return (
    <Widget
      title={t('level-of-fishing-protection')}
      lastUpdated={protectionLevelsData[0]?.attributes?.updatedAt}
      noData={noData}
      loading={loading}
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
