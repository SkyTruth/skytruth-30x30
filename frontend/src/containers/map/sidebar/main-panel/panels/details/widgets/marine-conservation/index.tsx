import { useMemo } from 'react';

import { groupBy, maxBy } from 'lodash-es';
import { useLocale, useTranslations } from 'next-intl';

import ConservationChart from '@/components/charts/conservation-chart';
import { Button } from '@/components/ui/button';
import Widget from '@/components/widget';
import { CUSTOM_REGION_CODE } from '@/containers/map/constants';
import { useSyncCustomRegion } from '@/containers/map/content/map/sync-settings';
import { useSyncMapContentSettings } from '@/containers/map/sync-settings';
import { formatKM, formatPercentage } from '@/lib/utils/formats';
import { FCWithMessages } from '@/types';
import { useGetAggregatedStats } from '@/types/generated/aggregated-stats';
import { useGetDataInfos } from '@/types/generated/data-info';
import type {
  LocationGroupsDataItemAttributes,
  AggregatedStats,
  AggregatedStatsEnvelope,
} from '@/types/generated/strapi.schemas';

import MissingCountriesList from '../widget-alerts/MissingCountriesList';

type MarineConservationWidgetProps = {
  location: LocationGroupsDataItemAttributes;
};

const MarineConservationWidget: FCWithMessages<MarineConservationWidgetProps> = ({ location }) => {
  const t = useTranslations('containers.map-sidebar-main-panel');
  const locale = useLocale();

  const [{ tab }, setSettings] = useSyncMapContentSettings();
  const [customRegionLocations] = useSyncCustomRegion();

  const locations =
    location.code === CUSTOM_REGION_CODE && customRegionLocations
      ? [...customRegionLocations].join(',')
      : location.code;

  const { data, isFetching } = useGetAggregatedStats<AggregatedStats[]>(
    {
      stats: 'protection_coverage',
      locations,
      environment: 'marine',
    },
    {
      query: {
        select: ({ data }) => data?.protection_coverage ?? [],
        placeholderData: { data: [] } as AggregatedStatsEnvelope,
        refetchOnWindowFocus: false,
      },
    }
  );

  const aggregatedData = useMemo(() => {
    if (!data?.length) return [];

    const groupedByYear = groupBy(data, 'year');

    return Object.keys(groupedByYear).map((year) => {
      const entries = groupedByYear[year];
      const protectedArea = entries[0].protected_area;
      const coverage = entries[0].coverage;
      const totalArea = entries[0].total_area ?? location.total_marine_area;
      const locations = entries[0].locations;

      return {
        year: Number(year),
        protectedArea,
        coverage,
        totalArea,
        locations,
      };
    });
  }, [data, location]);

  const { locations: mostLocsByYear } = useMemo(() => {
    if (!aggregatedData.length) return { locations: [] };

    return maxBy(aggregatedData, (entry) => entry.locations.length);
  }, [aggregatedData]);

  const missingLocations = useMemo(() => {
    const included = new Set(mostLocsByYear);
    const total = new Set(locations.split(','));

    return [...total.difference(included)];
  }, [mostLocsByYear, locations]);

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

    const { protectedArea, totalArea } = aggregatedData[aggregatedData.length - 1];
    const percentage =
      aggregatedData[aggregatedData.length - 1].coverage ?? (protectedArea / totalArea) * 100;
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

    const data = aggregatedData.reduce((acc, entry, index) => {
      if (entry.locations.length < mostLocsByYear.length) return acc;

      const isLastYear = index + 1 === aggregatedData.length;
      const { year, protectedArea, coverage } = entry;
      const percentage = coverage ?? (protectedArea * 100) / Number(entry.totalArea);

      acc.push({
        percentage,
        year,
        active: isLastYear,
        totalArea: Number(entry.totalArea),
        protectedArea,
        future: false,
      });

      return acc;
    }, []);

    return data;
  }, [aggregatedData, mostLocsByYear]);

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
    <>
      <Widget
        title={t('marine-conservation-coverage')}
        lastUpdated={data[data?.length - 1]?.updatedAt}
        noData={noData}
        loading={isFetching}
        info={metadata?.info}
        sources={metadata?.sources}
      >
        {stats && (
          <div className="mb-4 mt-6 flex flex-col">
            <span className="space-x-1">
              {t.rich('marine-protected-percentage', {
                b1: (chunks) => (
                  <span className="text-[64px] font-bold leading-[90%]">{chunks}</span>
                ),
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
        <MissingCountriesList countries={missingLocations} />
      </Widget>
    </>
  );
};

MarineConservationWidget.messages = [
  'containers.map-sidebar-main-panel',
  ...Widget.messages,
  ...ConservationChart.messages,
];

export default MarineConservationWidget;
