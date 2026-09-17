import { PropsWithChildren, useMemo } from 'react';

import theme from 'lib/tailwind';

import { useQueries } from '@tanstack/react-query';
import { useAtomValue } from 'jotai';
import { useLocale, useTranslations } from 'next-intl';

import StackedHorizontalBarChart from '@/components/charts/stacked-horizontal-bar-chart';
import TooltipButton from '@/components/tooltip-button';
import Widget from '@/components/widget';
import { drawStateAtom, modellingAtom } from '@/containers/map/store';
import { useSyncMapContentSettings } from '@/containers/map/sync-settings';
import { useFeatureFlag } from '@/hooks/use-feature-flag';
import useLocationName from '@/hooks/use-location-name';
import { cn } from '@/lib/classnames';
import { FCWithMessages } from '@/types';
import { useGetLocations } from '@/types/generated/location';
import { useGetMpaaProtectionLevelStats } from '@/types/generated/mpaa-protection-level-stat';
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

const EXISTING_AREA_COLOR = theme.colors.green as string;
const NEW_AREA_COLOR = theme.colors.black as string;
const FULLY_HIGHLY_PROTECTED_COLOR = theme.colors['green-dark'] as string;
const BECOMES_FULLY_HIGHLY_PROTECTED_COLOR = theme.colors['green-light'] as string;

const hatch = (color: string) =>
  `repeating-linear-gradient(45deg, ${color} 0 2px, transparent 2px 5px)`;
const FULLY_HIGHLY_PROTECTED_HATCH = hatch(FULLY_HIGHLY_PROTECTED_COLOR);
const BECOMES_FULLY_HIGHLY_PROTECTED_HATCH = hatch(BECOMES_FULLY_HIGHLY_PROTECTED_COLOR);

type FullyHighlyProtectedStats = {
  existingFullyHighlyProtectedPercentage: number;
  upgradedFullyHighlyProtectedPercentage: number;
};

type NationalLevelContribution = {
  location: Location;
  totalArea: number;
  totalProtectedArea: number;
  protectedArea: number;
  totalExistingAreaPercentage: number;
  totalCustomArea: number;
  totalCustomAreaPercentage: number;
  totalPercentage: number;
};

const getFullyHighlyProtectedStats = ({
  totalArea,
  protectedArea,
  totalProtectedArea,
  customArea,
  existingArea,
  newArea,
}: {
  totalArea: number;
  protectedArea: number;
  totalProtectedArea: number;
  customArea: number;
  existingArea: number;
  newArea: number;
}): FullyHighlyProtectedStats => {
  const existing = Math.min(Math.max(existingArea, 0), protectedArea);
  const added = Math.min(Math.max(newArea, 0), Math.max(totalProtectedArea - existing, 0));
  const upgraded = Math.min(Math.max(added - customArea, 0), protectedArea - existing);

  return {
    existingFullyHighlyProtectedPercentage: totalArea ? (existing / totalArea) * 100 : 0,
    upgradedFullyHighlyProtectedPercentage: totalArea ? (upgraded / totalArea) * 100 : 0,
  };
};

const getFullyHighlyProtectedOverlays = (
  stats: FullyHighlyProtectedStats & { totalExistingAreaPercentage: number }
) => {
  const upgradedStartPercentage =
    stats.totalExistingAreaPercentage - stats.upgradedFullyHighlyProtectedPercentage;

  return [
    {
      startPercentage: upgradedStartPercentage - stats.existingFullyHighlyProtectedPercentage,
      totalPercentage: stats.existingFullyHighlyProtectedPercentage,
      background: FULLY_HIGHLY_PROTECTED_HATCH,
      outlineColor: FULLY_HIGHLY_PROTECTED_COLOR,
    },
    {
      startPercentage: upgradedStartPercentage,
      totalPercentage: stats.upgradedFullyHighlyProtectedPercentage,
      background: BECOMES_FULLY_HIGHLY_PROTECTED_HATCH,
      outlineColor: BECOMES_FULLY_HIGHLY_PROTECTED_COLOR,
    },
  ].filter(({ totalPercentage }) => totalPercentage > 0);
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

const LEGEND_ITEM_CLASSES = 'relative pl-9 font-mono text-xs';
const LEGEND_LINE_CLASSES = cn(
  LEGEND_ITEM_CLASSES,
  'before:absolute before:left-0 before:top-1/2 before:h-[2px] before:w-[28px] before:-translate-y-1/2'
);

const LegendHatch: React.FC<{ backgroundColor: string; hatch: string; outlineColor: string }> = ({
  backgroundColor,
  hatch: background,
  outlineColor,
}) => (
  <span
    className="absolute left-0 top-1/2 h-2.5 w-[28px] -translate-y-1/2"
    style={{
      backgroundColor,
      backgroundImage: background,
      boxShadow: `inset 0 0 0 1px ${outlineColor}`,
    }}
  />
);

type WidgetLegendProps = {
  showBecomesFullyHighlyProtected?: boolean;
};

const WidgetLegend: FCWithMessages<WidgetLegendProps> = ({
  showBecomesFullyHighlyProtected = false,
}) => {
  const t = useTranslations('containers.map-sidebar-main-panel');
  const [{ tab }] = useSyncMapContentSettings();

  return (
    <ul>
      <li>
        <span className={cn(LEGEND_LINE_CLASSES, 'before:bg-green')}>
          {tab === 'marine' && t('marine-existing-conservation')}
          {tab === 'terrestrial' && t('terrestrial-existing-conservation')}
        </span>
      </li>
      {tab === 'marine' && (
        <li>
          <span className={LEGEND_ITEM_CLASSES}>
            <LegendHatch
              backgroundColor={EXISTING_AREA_COLOR}
              hatch={FULLY_HIGHLY_PROTECTED_HATCH}
              outlineColor={FULLY_HIGHLY_PROTECTED_COLOR}
            />
            {t('existing-fully-highly-protected')}
          </span>
        </li>
      )}
      {tab === 'marine' && showBecomesFullyHighlyProtected && (
        <li>
          <span className={LEGEND_ITEM_CLASSES}>
            <LegendHatch
              backgroundColor={NEW_AREA_COLOR}
              hatch={BECOMES_FULLY_HIGHLY_PROTECTED_HATCH}
              outlineColor={BECOMES_FULLY_HIGHLY_PROTECTED_COLOR}
            />
            {t('becomes-fully-highly-protected')}
          </span>
        </li>
      )}
      <li>
        <span className={cn(LEGEND_LINE_CLASSES, 'before:bg-black')}>{t('new-added-area')}</span>
      </li>
    </ul>
  );
};

WidgetLegend.messages = ['containers.map-sidebar-main-panel'];

const ModellingWidget: FCWithMessages = () => {
  const t = useTranslations('containers.map-sidebar-main-panel');
  const tUploads = useTranslations('services.uploads');
  const locale = useLocale();
  const getLocationName = useLocationName();

  const [{ tab }] = useSyncMapContentSettings();

  const chartsProps = DEFAULT_CHART_PROPS;

  const {
    status: modellingStatus,
    data: modellingData,
    errorMessage: errorMessageKey,
  } = useAtomValue(modellingAtom);

  const errorMessage = errorMessageKey
    ? tUploads(errorMessageKey as Parameters<typeof tUploads>[0], { environment: tab })
    : undefined;
  const { status: drawStatus } = useAtomValue(drawStateAtom);

  // Tooltips with mapping
  const tooltips = useTooltips();

  // TECH-3764: Clean up
  const isIhoActive = useFeatureFlag('is_iho_active');

  const locationQueries = useQueries({
    queries: (modellingData?.locations_area || []).map((location) =>
      getGetProtectionCoverageStatsQueryOptions<NationalLevelContribution | null>(
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
              fields: ['name', 'code', 'type', 'total_marine_area', 'total_terrestrial_area'],
            },
          },
          'pagination[limit]': 1,
          // @ts-ignore
          fields: ['protected_area', 'total_area'],
        },
        {
          query: {
            enabled:
              Boolean(modellingData?.locations_area) && ['marine', 'terrestrial'].includes(tab),
            select: ({ data }) => {
              if (!data?.length) return null;

              // existing protected area
              const protectedArea = data?.[0]?.protected_area ?? 0;
              const currentLoc = data?.[0]?.location;

              // Fallback area if location isn't in WDPA
              const fallBackArea =
                tab === 'marine'
                  ? currentLoc?.total_marine_area
                  : currentLoc?.total_terrestrial_area;

              const totalArea = Number(data?.[0]?.total_area ?? fallBackArea);
              // total custom protected area (analysis)
              const CLoc = modellingData.locations_area.find(
                ({ code }) => code === currentLoc?.code
              );

              const customArea = CLoc.protected_area;
              // If custom area exceeds total unprotected area, cap it to the total unprotected area
              // necessary because of rounding errors and differences in data resolutions
              const totalCustomArea =
                customArea + protectedArea > totalArea ? totalArea - protectedArea : customArea;
              // sum of existing protected area and custom protected area (analysis)
              const totalProtectedArea = protectedArea + totalCustomArea;
              // percentage of custom protected area (analysis)
              const totalCustomAreaPercentage = (totalCustomArea / totalArea) * 100;
              // percentage of existing protected area
              const totalExistingAreaPercentage = (protectedArea / totalArea) * 100;
              // percentage of existing protected area and custom protected area
              const totalPercentage = totalCustomAreaPercentage + totalExistingAreaPercentage;

              return {
                location: currentLoc,
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

  const loading =
    modellingStatus === 'running' ||
    drawStatus === 'uploading' ||
    locationQueries.some((query) => query.isInitialLoading);
  const error = modellingStatus === 'error';
  const loadingMessage =
    drawStatus === 'uploading' ? t('uploading-layer-to-map') : t('loading-data');

  // Seas overlap national waters, so they are excluded from the contributions and the global
  // total. Queried separately because the coverage stats above may have no row for a sea.
  const locationCodes = (modellingData?.locations_area || []).map(({ code }) => code);

  const { data: seaCodes } = useGetLocations<Set<string>>(
    {
      locale,
      // @ts-ignore
      fields: ['code'],
      filters: {
        code: {
          $in: locationCodes,
        },
        type: {
          $eq: 'sea',
        },
      },
      'pagination[limit]': locationCodes.length,
    },
    {
      query: {
        enabled: locationCodes.length > 0,
        select: ({ data }) => new Set(data.map(({ code }) => code)),
        placeholderData: { data: [] },
      },
    }
  );

  // Existing fully/highly protected area, per location and globally
  const { data: existingFullyHighlyProtectedAreas } = useGetMpaaProtectionLevelStats<
    Map<string, number>
  >(
    {
      locale,
      filters: {
        location: {
          code: {
            $in: [...locationCodes, 'GLOB'],
          },
        },
        mpaa_protection_level: {
          slug: {
            $eq: 'fully-highly-protected',
          },
        },
      },
      // @ts-ignore
      fields: ['area'],
      // @ts-ignore
      populate: {
        location: {
          fields: ['code'],
        },
      },
      'pagination[limit]': locationCodes.length + 1,
    },
    {
      query: {
        enabled: tab === 'marine' && locationCodes.length > 0,
        select: ({ data }) =>
          new Map(data.map(({ location, area }) => [location?.code, Number(area)])),
        placeholderData: { data: [] },
        refetchOnWindowFocus: false,
      },
    }
  );

  // Fully/highly protected area the drawn areas add, per location and globally
  const addedFullyHighlyProtectedAreas = useMemo(() => {
    const byLocation = new Map<string, number>();
    let total = 0;

    (modellingData?.fully_highly_protected?.locations_area || []).forEach(
      ({ code, protected_area }) => {
        byLocation.set(code, protected_area);
        if (!seaCodes?.has(code)) total += protected_area;
      }
    );

    return { byLocation, total };
  }, [modellingData, seaCodes]);

  const nationalLevelContributions = useMemo(
    () =>
      locationQueries
        .map((query) => {
          if (['loading', 'error'].includes(query.status)) return null;

          return query.data;
        })
        .filter((d): d is NationalLevelContribution => Boolean(d))
        // TECH-3764: Clean up
        .filter(({ location }) => isIhoActive || !seaCodes.has(location?.code))
        .map((contribution) => ({
          ...contribution,
          ...getFullyHighlyProtectedStats({
            totalArea: contribution.totalArea,
            protectedArea: contribution.protectedArea,
            totalProtectedArea: contribution.totalProtectedArea,
            customArea: contribution.totalCustomArea,
            existingArea: existingFullyHighlyProtectedAreas?.get(contribution.location?.code) ?? 0,
            newArea:
              addedFullyHighlyProtectedAreas.byLocation.get(contribution.location?.code) ?? 0,
          }),
        })),
    [
      locationQueries,
      seaCodes,
      isIhoActive,
      existingFullyHighlyProtectedAreas,
      addedFullyHighlyProtectedAreas,
    ]
  );

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
      fields: ['protected_area', 'total_area'],
    },
    {
      query: {
        queryKey: [modellingData, tab, locale],
        enabled: Boolean(modellingData?.locations_area) && ['marine', 'terrestrial'].includes(tab),
        select: ({ data }) => {
          if (!data) return null;

          // existing global protected area
          const protectedArea = data?.[0].protected_area ?? 0;
          // total area
          const totalArea = Number(data?.[0].total_area ?? 0);

          // total custom protected areas: filter out seas because they overlap
          // national waters
          const totalCustomAreas = modellingData.locations_area
            .filter(({ code }) => !seaCodes.has(code))
            .reduce((acc, { protected_area }) => acc + protected_area, 0);
          // sum of existing global protected area and custom protected areas (analysis)
          const totalProtectedArea = protectedArea + totalCustomAreas;
          // percentage of custom protected areas (analysis)
          const totalCustomAreasPercentage = (totalCustomAreas / totalArea) * 100;
          // percentage of existing global protected area
          const totalExistingAreaPercentage = (protectedArea / totalArea) * 100;
          // percentage of existing global protected area and custom protected areas
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

  const globalContribution = useMemo(() => {
    if (!globalProtectionStatsData) return null;

    return {
      ...globalProtectionStatsData,
      ...getFullyHighlyProtectedStats({
        totalArea: globalProtectionStatsData.totalArea,
        protectedArea: globalProtectionStatsData.protectedArea,
        totalProtectedArea: globalProtectionStatsData.totalProtectedArea,
        customArea: globalProtectionStatsData.totalCustomAreas,
        existingArea: existingFullyHighlyProtectedAreas?.get('GLOB') ?? 0,
        newArea: addedFullyHighlyProtectedAreas.total,
      }),
    };
  }, [
    globalProtectionStatsData,
    existingFullyHighlyProtectedAreas,
    addedFullyHighlyProtectedAreas,
  ]);

  const administrativeBoundaries = nationalLevelContributions.map((contribution) =>
    getLocationName(contribution.location)
  );

  const hasNationalUpgradedArea = nationalLevelContributions.some(
    ({ upgradedFullyHighlyProtectedPercentage }) => upgradedFullyHighlyProtectedPercentage > 0
  );
  const hasGlobalUpgradedArea =
    (globalContribution?.upgradedFullyHighlyProtectedPercentage ?? 0) > 0;

  return (
    <Widget
      className="border-black py-0"
      noData={!nationalLevelContributions.length}
      loading={loading}
      loadingMessage={loadingMessage}
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
            {administrativeBoundaries[0]}{' '}
            {administrativeBoundaries.length > 1 && `+${administrativeBoundaries.length - 1}`}
          </span>
        </div>
        <div className={cn(DEFAULT_ENTRY_CLASSNAMES)}>
          <div className="space-y-2">
            <WidgetSectionWidgetTitle
              title={t('national-level-contribution')}
              tooltip={tooltips?.['contributionDetails']}
            />
            <WidgetLegend showBecomesFullyHighlyProtected={hasNationalUpgradedArea} />
          </div>
          {nationalLevelContributions.map((contribution) => {
            const locationName = getLocationName(contribution.location);

            return (
              <StackedHorizontalBarChart
                key={contribution?.location?.code}
                title={locationName}
                customArea={contribution?.totalCustomArea}
                totalProtectedArea={contribution?.totalProtectedArea}
                totalArea={contribution?.totalArea}
                highlightedPercentage={contribution?.totalPercentage}
                {...(tab === 'marine' && {
                  overlays: getFullyHighlyProtectedOverlays(contribution),
                })}
                data={[
                  {
                    background: EXISTING_AREA_COLOR,
                    total: contribution?.protectedArea,
                    totalPercentage: contribution?.totalExistingAreaPercentage,
                  },
                  {
                    background: NEW_AREA_COLOR,
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
              title={t('global-contribution')}
              tooltip={tooltips?.['globalContribution']}
            />
            <WidgetLegend showBecomesFullyHighlyProtected={hasGlobalUpgradedArea} />
          </div>
          <StackedHorizontalBarChart
            title={t('global')}
            customArea={globalContribution?.totalCustomAreas}
            totalProtectedArea={globalContribution?.totalProtectedArea}
            totalArea={globalContribution?.totalArea}
            highlightedPercentage={globalContribution?.totalPercentage}
            {...(tab === 'marine' &&
              globalContribution && {
                overlays: getFullyHighlyProtectedOverlays(globalContribution),
              })}
            data={[
              {
                background: EXISTING_AREA_COLOR,
                total: globalContribution?.protectedArea,
                totalPercentage: globalContribution?.totalExistingAreaPercentage,
              },
              {
                background: NEW_AREA_COLOR,
                total: globalContribution?.totalCustomAreas,
                totalPercentage: globalContribution?.totalCustomAreasPercentage,
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
  'services.uploads',
  // Required by the `useLocationName` hook
  'locations',
  ...Widget.messages,
  ...WidgetLegend.messages,
  ...StackedHorizontalBarChart.messages,
];

export default ModellingWidget;
