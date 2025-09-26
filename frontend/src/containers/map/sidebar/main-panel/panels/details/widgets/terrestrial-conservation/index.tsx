import { useMemo } from 'react';

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

type TerrestrialConservationWidgetProps = {
  location: LocationGroupsDataItemAttributes;
};

const TerrestrialConservationWidget: FCWithMessages<TerrestrialConservationWidgetProps> = ({
  location,
}) => {
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
      environment: 'terrestrial',
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
    if (!data.length) return null;
    return {
      year: Number(data[data.length - 1].year),
      protectedArea: data[data.length - 1].protected_area,
      coverage: data[data.length - 1].coverage,
      totalArea: Number(data[data.length - 1]?.total_area ?? location.total_terrestrial_area),
      locations: data[data.length - 1].locations,
    };
  }, [data, location]);

  const missingLocations = useMemo(() => {
    const included = new Set(aggregatedData?.locations ?? []);
    const total = new Set(locations.split(','));

    return [...total.difference(included)];
  }, [aggregatedData, locations]);

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
    if (!aggregatedData) return null;
    const { protectedArea } = aggregatedData;
    const percentage = aggregatedData.coverage ?? (protectedArea / aggregatedData.totalArea) * 100;
    const percentageFormatted = formatPercentage(locale, percentage, {
      displayPercentageSign: false,
    });
    const protectedAreaFormatted = formatKM(locale, protectedArea);
    const totalAreaFormatted = formatKM(locale, aggregatedData.totalArea);

    return {
      protectedPercentage: percentageFormatted,
      protectedArea: protectedAreaFormatted,
      totalArea: totalAreaFormatted,
    };
  }, [locale, aggregatedData]);

  const noData = useMemo(() => {
    if (!aggregatedData) {
      return true;
    }
    return false;
  }, [aggregatedData]);

  return (
    <Widget
      title={t('terrestrial-conservation-coverage')}
      lastUpdated={data[data.length - 1]?.updatedAt}
      noData={noData}
      loading={isFetching}
      info={metadata?.info}
      sources={metadata?.sources}
    >
      {stats && (
        <div className="mb-4 mt-6 flex flex-col">
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
      <MissingCountriesList countries={missingLocations} />
    </Widget>
  );
};

TerrestrialConservationWidget.messages = [
  'containers.map-sidebar-main-panel',
  ...Widget.messages,
  ...ConservationChart.messages,
];

export default TerrestrialConservationWidget;
