import { PropsWithChildren, useMemo } from 'react';

import theme from 'lib/tailwind';

import { useQueries } from '@tanstack/react-query';
import { useAtomValue } from 'jotai';
import { useLocale, useTranslations } from 'next-intl';

import StackedHorizontalBarChart from '@/components/charts/stacked-horizontal-bar-chart';
import TooltipButton from '@/components/tooltip-button';
import Widget from '@/components/widget';
import { modellingAtom } from '@/containers/map/store';
import { useSyncMapContentSettings } from '@/containers/map/sync-settings';
import useNameField from '@/hooks/use-name-field';
import { cn } from '@/lib/classnames';
import { FCWithMessages } from '@/types';
import {
  getGetProtectionCoverageStatsQueryOptions,
  useGetProtectionCoverageStats,
} from '@/types/generated/protection-coverage-stat';
import { Location } from '@/types/generated/strapi.schemas';

import useTooltips from '../useTooltips';

const DEFAULT_ENTRY_CLASSNAMES = 'border-t border-black py-6';

const DEFAULT_CHART_PROPS = {
  className: 'py-2',
  showLegend: false,
  showTarget: false,
};

type WidgetSectionWidgetTitleProps = PropsWithChildren<{
  title: string;
  tooltip?: string;
}>;

const WidgetSectionWidgetTitle: React.FC<WidgetSectionWidgetTitleProps> = ({ title, tooltip }) => {
  return (
    <div className="flex items-center">
      <span className="font-mono text-xs uppercase">{title}</span>
      {tooltip && <TooltipButton className="-mt-1" text={tooltip} />}
    </div>
  );
};

const WidgetLegend: FCWithMessages = () => {
  const t = useTranslations('containers.map-sidebar-main-panel');
  const [{ tab }] = useSyncMapContentSettings();

  const LEGEND_LINE_CLASSES =
    'relative pl-9 font-mono text-xs before:absolute before:left-0 before:top-1/2 before:h-[2px] before:w-[28px] before:-translate-y-1/2';

  return (
    <ul>
      <li>
        <span className={cn(LEGEND_LINE_CLASSES, 'before:bg-green')}>
          {tab === 'marine' && t('marine-existing-conservation')}
          {tab === 'terrestrial' && t('terrestrial-existing-conservation')}
        </span>
      </li>
      <li>
        <span className={cn(LEGEND_LINE_CLASSES, 'before:bg-black')}>{t('new-added-area')}</span>
      </li>
    </ul>
  );
};

WidgetLegend.messages = ['containers.map-sidebar-main-panel'];

const ModellingWidget: FCWithMessages = () => {
  const t = useTranslations('containers.map-sidebar-main-panel');
  const locale = useLocale();
  const locationNameField = useNameField();

  const [{ tab }] = useSyncMapContentSettings();

  const chartsProps = DEFAULT_CHART_PROPS;

  const {
    status: modellingStatus,
    data: modellingData,
    errorMessage,
  } = useAtomValue(modellingAtom);

  // Tooltips with mapping
  const tooltips = useTooltips();

  const { data: globalProtectionStatsData } = useGetProtectionCoverageStats<{
    protectedArea: number;
    percentageProtectedArea: number;
    totalArea: number;
    totalProtectedArea: number;
    totalPercentage: number;
    totalCustomAreas: number;
    totalExistingAreaPercentage: number;
    totalCustomAreasPercentage: number;
  }>(
    {
      locale,
      filters: {
        location: {
          code: 'GLOB',
        },
        is_last_year: {
          $eq: true,
        },
        environment: {
          slug: {
            $eq: tab,
          },
        },
      },
      // @ts-ignore
      populate: {
        location: {
          fields: ['total_marine_area', 'total_terrestrial_area'],
        },
      },
      'pagination[limit]': 1,
      // @ts-ignore
      fields: ['protected_area'],
    },
    {
      query: {
        enabled: Boolean(modellingData?.locations_area) && ['marine', 'terrestrial'].includes(tab),
        select: ({ data }) => {
          if (!data) return null;

          const protectedArea = data?.[0].attributes.protected_area ?? 0;

          const location = data?.[0].attributes?.location?.data?.attributes;
          let totalArea;
          if (tab === 'marine') {
            totalArea = location?.total_marine_area ? Number(location?.total_marine_area) : 0;
          } else {
            totalArea = location?.total_terrestrial_area
              ? Number(location?.total_terrestrial_area)
              : 0;
          }

          const totalCustomAreas = modellingData.locations_area.reduce((acc, location) => {
            return acc + location.protected_area;
          }, 0);

          const totalProtectedArea = protectedArea + totalCustomAreas;
          //  ? percentage of custom protected areas (analysis)
          const totalCustomAreasPercentage = (totalCustomAreas / totalArea) * 100;
          //  ? percentage of existing global protected area
          const totalExistingAreaPercentage = (protectedArea / totalArea) * 100;

          const totalPercentage = totalCustomAreasPercentage + totalExistingAreaPercentage;

          return {
            protectedArea,
            percentageProtectedArea: (protectedArea / totalArea) * 100,
            totalArea,
            totalProtectedArea,
            totalPercentage,
            totalCustomAreas,
            totalExistingAreaPercentage,
            totalCustomAreasPercentage,
          };
        },
        refetchOnWindowFocus: false,
      },
    }
  );

  const locationQueries = useQueries({
    queries: (modellingData?.locations_area || []).map((location) =>
      getGetProtectionCoverageStatsQueryOptions(
        {
          locale,
          filters: {
            location: {
              code: location.code,
            },
            is_last_year: {
              $eq: true,
            },
            environment: {
              slug: {
                $eq: tab,
              },
            },
          },
          // @ts-ignore
          populate: {
            location: {
              fields: [
                'name',
                'name_es',
                'name_fr',
                'name_pt',
                'code',
                'total_marine_area',
                'total_terrestrial_area',
              ],
            },
          },
          'pagination[limit]': 1,
          // @ts-ignore
          fields: ['protected_area'],
        },
        {
          query: {
            enabled:
              Boolean(modellingData?.locations_area) && ['marine', 'terrestrial'].includes(tab),
            select: ({ data }) => {
              if (!data) return null;

              const protectedArea = data?.[0]?.attributes.protected_area ?? 0;

              const location = data?.[0]?.attributes?.location?.data?.attributes;

              // ? total extension of location
              let totalArea;
              if (tab === 'marine') {
                totalArea = location?.total_marine_area ? Number(location.total_marine_area) : 0;
              } else {
                totalArea = location?.total_terrestrial_area
                  ? Number(location.total_terrestrial_area)
                  : 0;
              }

              // ? total custom  protected area (analysis)
              const totalCustomArea = modellingData.locations_area.find(
                ({ code }) => code === location?.code
              ).protected_area;

              //  ? percentage of custom protected area (analysis)
              const totalCustomAreaPercentage = (totalCustomArea / totalArea) * 100;
              //  ? percentage of existing protected area
              const totalExistingAreaPercentage = (protectedArea / totalArea) * 100;

              // ? sum of existing protected area and protected custom area (analysis)
              const totalProtectedArea = protectedArea + totalCustomArea;

              const totalPercentage = totalCustomAreaPercentage + totalExistingAreaPercentage;

              return {
                location,
                totalArea,
                totalProtectedArea,
                protectedArea,
                totalExistingAreaPercentage,
                totalCustomArea,
                totalCustomAreaPercentage,
                totalPercentage,
              };
            },
            refetchOnWindowFocus: false,
          },
        }
      )
    ),
  });

  const loading = modellingStatus === 'running';
  const error = modellingStatus === 'error';

  // @ts-expect-error will check later
  const nationalLevelContributions: {
    location: Location;
    percentageProtectedArea: number;
    totalArea: number;
    totalProtectedArea: number;
    protectedArea: number;
    totalExistingAreaPercentage: number;
    totalCustomArea: number;
    totalCustomAreaPercentage: number;
    totalPercentage: number;
  }[] = useMemo(
    () =>
      locationQueries
        .map((query) => {
          if (['loading', 'error'].includes(query.status)) return null;

          return query.data;
        })
        .filter((d) => Boolean(d)),
    [locationQueries]
  );

  const administrativeBoundaries = nationalLevelContributions?.map((contribution) => {
    const locationName = contribution.location[locationNameField];
    return locationName;
  });

  return (
    <Widget
      className="border-b border-black py-0"
      noData={!nationalLevelContributions}
      loading={loading}
      error={error}
      errorMessage={errorMessage}
    >
      <div className="flex flex-col">
        <div className={cn(DEFAULT_ENTRY_CLASSNAMES, 'flex justify-between border-t-0')}>
          <WidgetSectionWidgetTitle
            title={t('administrative-boundary')}
            tooltip={tooltips?.['administrativeBoundary']}
          />
          <span className="text-right font-mono text-xs font-bold underline">
            {administrativeBoundaries?.[0]}{' '}
            {administrativeBoundaries?.length > 1 && `+${administrativeBoundaries?.length - 1}`}
          </span>
        </div>
        <div className={cn(DEFAULT_ENTRY_CLASSNAMES)}>
          <div className="space-y-2">
            <WidgetSectionWidgetTitle
              title={t('national-level-contribution')}
              tooltip={tooltips?.['contributionDetails']}
            />
            <WidgetLegend />
          </div>
          {nationalLevelContributions?.map((contribution) => {
            const locationName = contribution.location[locationNameField];

            return (
              <StackedHorizontalBarChart
                key={contribution?.location?.code}
                title={locationName}
                customArea={contribution?.totalCustomArea}
                totalProtectedArea={contribution?.totalProtectedArea}
                totalArea={contribution?.totalArea}
                highlightedPercentage={contribution?.totalPercentage}
                data={[
                  {
                    background: theme.colors.green as string,
                    total: contribution?.protectedArea,
                    totalPercentage: contribution?.totalExistingAreaPercentage,
                  },
                  {
                    background: theme.colors.black as string,
                    total: contribution?.totalCustomArea,
                    totalPercentage: contribution?.totalCustomAreaPercentage,
                  },
                ]}
                {...chartsProps}
              />
            );
          })}
        </div>
        <div className={cn(DEFAULT_ENTRY_CLASSNAMES)}>
          <div className="space-y-2">
            <WidgetSectionWidgetTitle
              title="Global level contribution"
              tooltip={tooltips?.['globalContribution']}
            />
            <WidgetLegend />
          </div>
          <StackedHorizontalBarChart
            title={t('global')}
            customArea={globalProtectionStatsData?.totalCustomAreas}
            totalProtectedArea={globalProtectionStatsData?.totalProtectedArea}
            totalArea={globalProtectionStatsData?.totalArea}
            highlightedPercentage={globalProtectionStatsData?.totalPercentage}
            data={[
              {
                background: theme.colors.green as string,
                total: globalProtectionStatsData?.protectedArea,
                totalPercentage: globalProtectionStatsData?.totalExistingAreaPercentage,
              },
              {
                background: theme.colors.black as string,
                total: globalProtectionStatsData?.totalCustomAreas,
                totalPercentage: globalProtectionStatsData?.totalCustomAreasPercentage,
              },
            ]}
            {...chartsProps}
            showTarget
          />
        </div>
      </div>
    </Widget>
  );
};

ModellingWidget.messages = [
  'containers.map-sidebar-main-panel',
  ...Widget.messages,
  ...WidgetLegend.messages,
  ...StackedHorizontalBarChart.messages,
];

export default ModellingWidget;
