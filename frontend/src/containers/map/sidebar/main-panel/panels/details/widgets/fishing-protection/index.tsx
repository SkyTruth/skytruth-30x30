import { useMemo } from 'react';

import { useLocale, useTranslations } from 'next-intl';

import HorizontalBarChart from '@/components/charts/horizontal-bar-chart';
import Widget from '@/components/widget';
import { FISHING_PROTECTION_CHART_COLORS } from '@/constants/fishing-protection-chart-colors';
import { FCWithMessages } from '@/types';
import { useGetDataInfos } from '@/types/generated/data-info';
import { useGetFishingProtectionLevelStats } from '@/types/generated/fishing-protection-level-stat';
import type { LocationGroupsDataItemAttributes } from '@/types/generated/strapi.schemas';

type FishingProtectionWidgetProps = {
  location: LocationGroupsDataItemAttributes;
};

const FishingProtectionWidget: FCWithMessages<FishingProtectionWidgetProps> = ({ location }) => {
  const t = useTranslations('containers.map-sidebar-main-panel');
  const locale = useLocale();

  const {
    data: { data: fishingProtectionLevelsData },
    isFetching,
  } = useGetFishingProtectionLevelStats(
    {
      filters: {
        location: {
          code: location?.code,
        },
        fishing_protection_level: {
          slug: 'highly',
        },
      },
      // eslint-disable-next-line @typescript-eslint/ban-ts-comment
      // @ts-ignore
      populate: {
        fields: ['area', 'pct', 'total_area', 'updatedAt'],
        fishing_protection_level: {
          fields: ['slug'],
        },
      },
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
    const parsedProtectionLevel = (label: string, protectionLevel, stats) => {
      return {
        title: label,
        slug: protectionLevel,
        background: FISHING_PROTECTION_CHART_COLORS[protectionLevel],
        totalArea: stats.total_area ?? location?.total_marine_area,
        protectedArea: stats.area,
        percentage: stats.pct,
        info: metadata?.info,
        sources: metadata?.sources,
        updatedAt: stats.updatedAt,
      };
    };

    const parsedFishingProtectionLevelData = fishingProtectionLevelsData?.map((stats) => {
      const data = stats?.attributes;
      const protectionLevel = data?.fishing_protection_level?.data.attributes.slug;

      return parsedProtectionLevel(t('highly-protected-from-fishing'), protectionLevel, data);
    });

    return parsedFishingProtectionLevelData?.filter(Boolean) ?? [];
  }, [t, fishingProtectionLevelsData, metadata, location]);

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
