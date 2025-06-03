import { useMemo } from 'react';

import { groupBy } from 'lodash-es';
import { useLocale, useTranslations } from 'next-intl';

import ConservationChart from '@/components/charts/conservation-chart';
import { Button } from '@/components/ui/button';
import Widget from '@/components/widget';
import { useSyncMapContentSettings } from '@/containers/map/sync-settings';
import { formatKM, formatPercentage } from '@/lib/utils/formats';
import { FCWithMessages } from '@/types';
import { useGetDataInfos } from '@/types/generated/data-info';
import { useGetProtectionCoverageStats } from '@/types/generated/protection-coverage-stat';
import type {
  LocationGroupsDataItemAttributes,
  ProtectionCoverageStatListResponseDataItem,
} from '@/types/generated/strapi.schemas';

type MarineConservationWidgetProps = {
  location: LocationGroupsDataItemAttributes;
};

const MarineConservationWidget: FCWithMessages<MarineConservationWidgetProps> = ({ location }) => {
  const t = useTranslations('containers.map-sidebar-main-panel');
  const locale = useLocale();

  const [{ tab }, setSettings] = useSyncMapContentSettings();

  const { data, isFetching } = useGetProtectionCoverageStats<
    ProtectionCoverageStatListResponseDataItem[]
  >(
    {
      locale,
      // eslint-disable-next-line @typescript-eslint/ban-ts-comment
      // @ts-ignore
      populate: {
        location: {
          fields: ['code', 'total_marine_area', 'marine_target', 'marine_target_year'],
        },
        environment: {
          fields: ['slug'],
        },
      },
      sort: 'year:asc',
      'pagination[limit]': -1,
      // eslint-disable-next-line @typescript-eslint/ban-ts-comment
      // @ts-ignore
      fields: ['year', 'protected_area', 'updatedAt', 'coverage'],
      filters: {
        location: {
          code: {
            $eq: location?.code || 'GLOB',
          },
        },
        environment: {
          slug: {
            $eq: 'marine',
          },
        },
      },
    },
    {
      query: {
        select: ({ data }) => data ?? [],
        placeholderData: [],
        refetchOnWindowFocus: false,
      },
    }
  );

  const aggregatedData = useMemo(() => {
    if (!data.length) return [];

    const groupedByYear = groupBy(data, 'attributes.year');

    return Object.keys(groupedByYear).map((year) => {
      const entries = groupedByYear[year];
      const protectedArea = entries[0].attributes.protected_area;
      const coverage = entries[0].attributes.coverage;

      return {
        year: Number(year),
        protectedArea,
        coverage
      };
    });
  }, [data]);

  const { data: metadata } = useGetDataInfos(
    {
      locale,
      filters: {
        slug: 'coverage-widget',
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

  const stats = useMemo(() => {
    if (!aggregatedData.length) return null;

    const totalArea = Number(location.total_marine_area);
    const { protectedArea } = aggregatedData[aggregatedData.length - 1];
    const percentage = aggregatedData[aggregatedData.length - 1].coverage ?? ((protectedArea / totalArea) * 100) 
    const percentageFormatted = formatPercentage(locale, percentage, {
      displayPercentageSign: false,
    });
    const protectedAreaFormatted = formatKM(locale, protectedArea);
    const totalAreaFormatted = formatKM(locale, totalArea);

    return {
      protectedPercentage: percentageFormatted,
      protectedArea: protectedAreaFormatted,
      totalArea: totalAreaFormatted,
      target: location.marine_target,
      targetYear: location.marine_target_year,
    };
  }, [locale, location, aggregatedData]);

  const chartData = useMemo(() => {
    if (!aggregatedData.length) return [];

    const data = aggregatedData.map((entry, index) => {
      const isLastYear = index + 1 === aggregatedData.length;
      const { year, protectedArea } = entry;
      const percentage = (protectedArea * 100) / Number(location.total_marine_area);

      return {
        // We only want to show up to 55%, so we'll cap the percentage here
        // Some of the data seems incorrect; this is a quick fix in order to not blow the chart
        percentage: percentage > 55 ? 55 : percentage,
        year,
        active: isLastYear,
        totalArea: Number(location.total_marine_area),
        protectedArea,
        future: false,
      };
    });

    return data;
  }, [location, aggregatedData]);

  const noData = useMemo(() => {
    if (!chartData.length) {
      return true;
    }

    const emptyValues = chartData.every((d) => d.percentage === 0);
    if (emptyValues) {
      return true;
    }

    return false;
  }, [chartData]);

  return (
    <Widget
      title={t('marine-conservation-coverage')}
      lastUpdated={data[data.length - 1]?.attributes.updatedAt}
      noData={noData}
      loading={isFetching}
      info={metadata?.info}
      sources={metadata?.sources}
    >
      {stats && (
        <div className="mb-4 mt-6 flex flex-col">
          <span className="space-x-1">
            {t.rich('marine-protected-percentage', {
              b1: (chunks) => <span className="text-[64px] font-bold leading-[90%]">{chunks}</span>,
              b2: (chunks) => <span className="text-lg">{chunks}</span>,
              percentage: stats?.protectedPercentage,
            })}
          </span>
          <span className="space-x-1 text-xs">
            <span>
              {t('marine-protected-area', {
                protectedArea: stats?.protectedArea,
                totalArea: stats?.totalArea,
              })}
            </span>
          </span>
        </div>
      )}
      <ConservationChart
        className="-ml-8 aspect-[16/10]"
        tooltipSlug="30x30-marine-target"
        data={chartData}
        displayTarget={!!stats?.target}
        target={stats?.target ?? undefined}
        targetYear={stats?.targetYear ?? undefined}
      />
      {tab !== 'marine' && (
        <Button
          variant="white"
          size="full"
          className="mt-5 flex h-10 px-5 md:px-8"
          onClick={() => setSettings((settings) => ({ ...settings, tab: 'marine' }))}
        >
          <span className="font-mono text-xs font-semibold normal-case">
            {t('explore-marine-conservation')}
          </span>
        </Button>
      )}
    </Widget>
  );
};

MarineConservationWidget.messages = [
  'containers.map-sidebar-main-panel',
  ...Widget.messages,
  ...ConservationChart.messages,
];

export default MarineConservationWidget;
