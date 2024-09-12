import { useMemo } from 'react';

import { groupBy } from 'lodash-es';
import { useLocale, useTranslations } from 'next-intl';

import ConservationChart from '@/components/charts/conservation-chart';
import { Button } from '@/components/ui/button';
import Widget from '@/components/widget';
import { useSyncMapContentSettings } from '@/containers/map/sync-settings';
import { formatKM } from '@/lib/utils/formats';
import { formatPercentage } from '@/lib/utils/formats';
import { FCWithMessages } from '@/types';
import { useGetDataInfos } from '@/types/generated/data-info';
import { useGetProtectionCoverageStats } from '@/types/generated/protection-coverage-stat';
import type {
  LocationGroupsDataItemAttributes,
  ProtectionCoverageStatListResponseDataItem,
} from '@/types/generated/strapi.schemas';

type TerrestrialConservationWidgetProps = {
  location: LocationGroupsDataItemAttributes;
};

const TerrestrialConservationWidget: FCWithMessages<TerrestrialConservationWidgetProps> = ({
  location,
}) => {
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
          fields: ['code', 'totalTerrestrialArea'],
        },
        environment: {
          fields: ['slug'],
        },
      },
      sort: 'year:asc',
      'pagination[limit]': -1,
      // eslint-disable-next-line @typescript-eslint/ban-ts-comment
      // @ts-ignore
      fields: ['year', 'cumSumProtectedArea', 'updatedAt'],
      filters: {
        location: {
          code: {
            $eq: location?.code || 'GLOB',
          },
        },
        environment: {
          slug: {
            $eq: 'terrestrial',
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
      const protectedArea = entries.reduce(
        (acc, entry) => acc + entry.attributes.cumSumProtectedArea,
        0
      );

      return {
        year: Number(year),
        protectedArea,
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

  const stats = useMemo(() => {
    if (!aggregatedData.length) return null;

    const totalArea = location.totalMarineArea;
    const { protectedArea } = aggregatedData[0];
    const percentageFormatted = formatPercentage(locale, (protectedArea / totalArea) * 100, {
      displayPercentageSign: false,
    });
    const protectedAreaFormatted = formatKM(locale, protectedArea);
    const totalAreaFormatted = formatKM(locale, totalArea);

    return {
      protectedPercentage: percentageFormatted,
      protectedArea: protectedAreaFormatted,
      totalArea: totalAreaFormatted,
    };
  }, [locale, location, aggregatedData]);

  const chartData = useMemo(() => {
    if (!aggregatedData.length) return [];

    const data = aggregatedData.map((entry, index) => {
      const isLastYear = index + 1 === aggregatedData.length;
      const { year, protectedArea } = entry;
      const percentage = (protectedArea * 100) / location.totalMarineArea;

      return {
        // We only want to show up to 55%, so we'll cap the percentage here
        // Some of the data seems incorrect; this is a quick fix in order to not blow the chart
        percentage: percentage > 55 ? 55 : percentage,
        year,
        active: isLastYear,
        totalArea: location.totalMarineArea,
        protectedArea,
        future: false,
      };
    });

    return data;
  }, [location, aggregatedData]);

  return (
    <Widget
      title={t('terrestrial-conservation-coverage')}
      lastUpdated={data[data.length - 1]?.attributes.updatedAt}
      noData={!chartData.length}
      loading={isFetching}
      info={metadata?.info}
      sources={metadata?.sources}
    >
      {stats && (
        <div className="mt-6 mb-4 flex flex-col">
          <span className="space-x-1">
            {t.rich('terrestrial-protected-percentage', {
              b1: (chunks) => <span className="text-[64px] font-bold leading-[90%]">{chunks}</span>,
              b2: (chunks) => <span className="text-lg">{chunks}</span>,
              percentage: stats?.protectedPercentage,
            })}
          </span>
          <span className="space-x-1 text-xs">
            <span>
              {t('terrestrial-protected-area', {
                protectedArea: stats?.protectedArea,
                totalArea: stats?.totalArea,
              })}
            </span>
          </span>
        </div>
      )}
      <ConservationChart
        className="-ml-8 aspect-[16/10]"
        displayTarget={location?.code === 'GLOB'}
        data={chartData}
      />
      {tab !== 'terrestrial' && (
        <Button
          variant="white"
          size="full"
          className="mt-5 flex h-10 px-5 md:px-8"
          onClick={() => setSettings((settings) => ({ ...settings, tab: 'terrestrial' }))}
        >
          <span className="font-mono text-xs font-semibold normal-case">
            {t('explore-terrestrial-conservation')}
          </span>
        </Button>
      )}
    </Widget>
  );
};

TerrestrialConservationWidget.messages = [
  'containers.map-sidebar-main-panel',
  ...Widget.messages,
  ...ConservationChart.messages,
];

export default TerrestrialConservationWidget;
