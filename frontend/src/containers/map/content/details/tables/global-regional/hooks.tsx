import { useMemo } from 'react';

import Link from 'next/link';

import { AccessorKeyColumnDef, PaginationState, SortingState } from '@tanstack/react-table';
import { useLocale, useTranslations } from 'next-intl';

import FiltersButton from '@/components/filters-button';
import type { Source } from '@/components/tooltip-button';
import Icon from '@/components/ui/icon';
import { PAGES } from '@/constants/pages';
import { NEW_LOCS } from '@/constants/territories'; // TODO TECH-3174: Clean up
import HeaderItem from '@/containers/map/content/details/table/header-item';
import { cellFormatter } from '@/containers/map/content/details/table/helpers';
import SortingButton from '@/containers/map/content/details/table/sorting-button';
import TooltipButton from '@/containers/map/content/details/table/tooltip-button';
import {
  useMapSearchParams,
  useSyncCustomRegion,
} from '@/containers/map/content/map/sync-settings';
import { useFeatureFlag } from '@/hooks/use-feature-flag'; // TODO TECH-3174: Clean up
import Mountain from '@/styles/icons/mountain.svg';
import Wave from '@/styles/icons/wave.svg';
import { useGetDataInfos } from '@/types/generated/data-info';
import { useGetEnvironments } from '@/types/generated/environment';
import { useGetLocations } from '@/types/generated/location';
import { useGetProtectionCoverageStats } from '@/types/generated/protection-coverage-stat';
import { ProtectionCoverageStatListResponseMetaPagination } from '@/types/generated/strapi.schemas';

export type GlobalRegionalTableColumns = {
  location: {
    name: string;
    name_es: string;
    name_fr: string;
    code: string;
    mpaa_protection_level_stats: {
      percentage: number;
    };
  };
  environment: {
    name: string;
    slug: string;
  };
  coverage: number;
  protected_area: number;
  pas: number;
  oecms: number;
  global_contribution: number;
};

const TOOLTIP_MAPPING = {
  environment: 'environment',
  location: 'name-country',
  coverage: 'coverage',
  pas: 'pas',
  oecms: 'oecms',
  protectedArea: 'protected-area',
  fullyHighlyProtected: 'fully-highly-protected',
  globalContribution: 'global-contribution',
};

const useTooltips = () => {
  const locale = useLocale();

  const { data: dataInfo } = useGetDataInfos(
    {
      locale,
      populate: 'data_sources',
      filters: {
        slug: {
          $in: Object.entries(TOOLTIP_MAPPING).map((entry) => entry[1]),
        },
      },
    },
    {
      query: {
        select: ({ data }) => data,
        placeholderData: { data: [] },
      },
    }
  );
  const tooltips: {
    [key: string]: {
      text: string;
      sources: Source[];
    };
  } = {};

  Object.entries(TOOLTIP_MAPPING).map(([key, value]) => {
    const tooltip = dataInfo.find(({ attributes }) => attributes.slug === value)?.attributes;

    if (!tooltip) return;
    const sources = !!tooltip?.data_sources?.data?.length
      ? tooltip?.data_sources?.data.map(
          ({ id, attributes: { slug, title = null, url = null } }) => {
            return { id, slug, url, title };
          }
        )
      : null;

    tooltips[key] = { text: tooltip?.content, sources };
  });

  return tooltips;
};

const useFiltersOptions = () => {
  const locale = useLocale();

  const { data: environmentOptions } = useGetEnvironments<{ name: string; value: string }[]>(
    {
      locale,
      // @ts-ignore
      fields: ['name', 'slug'],
      'pagination[limit]': -1,
    },
    {
      query: {
        select: ({ data }) =>
          data.map((environment) => ({
            name: environment.attributes.name,
            value: environment.attributes.slug,
          })),
        placeholderData: { data: [] },
      },
    }
  );

  return {
    environment: environmentOptions,
  };
};

export const useColumns = (
  environment: 'marine' | 'terrestrial' | null,
  filters: Record<string, string[]>,
  onChangeFilters: (newFilters: Record<string, string[]>) => void
) => {
  const t = useTranslations('containers.map');
  const locale = useLocale();

  const searchParams = useMapSearchParams();
  const tooltips = useTooltips();

  const filtersOptions = useFiltersOptions();

  const columns: AccessorKeyColumnDef<GlobalRegionalTableColumns>[] = useMemo(() => {
    let locationNameKey = 'name';
    if (locale === 'es') {
      locationNameKey = 'name_es';
    } else if (locale === 'fr') {
      locationNameKey = 'name_fr';
    }

    return [
      {
        id: `location.${locationNameKey}`,
        accessorKey: `location.${locationNameKey}`,
        header: ({ column }) => (
          <HeaderItem className="ml-1">
            <SortingButton column={column} />
            {t('name')}
            <TooltipButton tooltip={tooltips?.location} />
          </HeaderItem>
        ),
        cell: ({ row }) => {
          const { location, environment } = row.original;
          return (
            <HeaderItem>
              {environment.slug === 'marine' && <Icon icon={Wave} className="mr-1.5 w-[14px]" />}
              {environment.slug === 'terrestrial' && (
                <Icon icon={Mountain} className="mr-1.5 w-[14px]" />
              )}
              <Link
                className="font-semibold underline"
                href={`${PAGES.progressTracker}/${location.code}?${searchParams.toString()}`}
              >
                {location[locationNameKey]}
              </Link>
            </HeaderItem>
          );
        },
      },
      {
        id: 'environment.name',
        accessorKey: 'environment.name',
        header: () => (
          <HeaderItem className="ml-1">
            {!environment && (
              <FiltersButton
                field="environment.slug"
                options={filtersOptions.environment}
                values={filters['environment.slug'] ?? []}
                onChange={(field, values) => onChangeFilters({ ...filters, [field]: values })}
              />
            )}
            {t('ecosystem')}
            <TooltipButton tooltip={tooltips?.environment} />
          </HeaderItem>
        ),
        cell: ({ row }) => {
          const { environment } = row.original;
          return <HeaderItem>{environment.name}</HeaderItem>;
        },
      },
      {
        id: 'coverage',
        accessorKey: 'coverage',
        header: ({ column }) => (
          <HeaderItem>
            <SortingButton column={column} />
            {t('coverage')}
            <TooltipButton tooltip={tooltips?.coverage} />
          </HeaderItem>
        ),
        cell: ({ row }) => {
          const { coverage: value } = row.original;
          const formattedCoverage = cellFormatter.percentage(locale, value);

          return (
            <span className="text-4xl font-bold">
              {t.rich('percentage-bold', {
                b1: (chunks) => chunks,
                b2: (chunks) => <span className="text-xs">{chunks}</span>,
                percentage: formattedCoverage,
              })}
            </span>
          );
        },
      },
      {
        id: 'protected-area',
        accessorKey: 'protected-area',
        header: ({ column }) => (
          <HeaderItem>
            <SortingButton column={column} />
            {t('area')}
            <TooltipButton tooltip={tooltips?.protectedArea} />
          </HeaderItem>
        ),
        cell: ({ row }) => {
          const { protected_area: value } = row.original;
          const formattedValue = cellFormatter.area(locale, value);
          return <span>{t('area-km2', { area: formattedValue })}</span>;
        },
      },
      {
        id: 'pas',
        accessorKey: 'pas',
        header: ({ column }) => (
          <HeaderItem>
            <SortingButton column={column} />
            {t('pas')}
            <TooltipButton tooltip={tooltips.pas} />
          </HeaderItem>
        ),
        cell: ({ row }) => {
          const { pas: value } = row.original;
          if (Number.isNaN(value)) return t('n-a');

          const formattedValue = cellFormatter.percentage(locale, value);
          return <span className="text-xs">{t('percentage', { percentage: formattedValue })}</span>;
        },
      },
      {
        id: 'oecms',
        accessorKey: 'oecms',
        header: ({ column }) => (
          <HeaderItem>
            <SortingButton column={column} />
            {t('oecms')}
            <TooltipButton tooltip={tooltips?.oecms} />
          </HeaderItem>
        ),
        cell: ({ row }) => {
          const { oecms: value } = row.original;
          if (Number.isNaN(value)) return t('n-a');

          const formattedValue = cellFormatter.percentage(locale, value);
          return <span className="text-xs">{t('percentage', { percentage: formattedValue })}</span>;
        },
      },
      ...(environment === 'marine'
        ? [
            {
              id: 'location.mpaa_protection_level_stats.percentage',
              accessorKey: 'location.mpaa_protection_level_stats.percentage',
              header: ({ column }) => (
                <HeaderItem>
                  <SortingButton column={column} />
                  {t('fully-highly-protected')}
                  <TooltipButton tooltip={tooltips?.fullyHighlyProtected} />
                </HeaderItem>
              ),
              cell: ({ row }) => {
                const { location } = row.original;

                const value = location.mpaa_protection_level_stats.percentage;
                if (value === null || value === undefined) {
                  return <span className="text-xs">{t('no-data-available')}</span>;
                }

                const formattedValue = cellFormatter.percentage(locale, value ?? 0);

                return (
                  <span className="text-xs">{t('percentage', { percentage: formattedValue })}</span>
                );
              },
            },
          ]
        : []),
      {
        id: 'global_contribution',
        accessorKey: 'global_contribution',
        header: ({ column }) => (
          <HeaderItem>
            <SortingButton column={column} />
            {t('global-contribution')}
            <TooltipButton tooltip={tooltips?.globalContribution} />
          </HeaderItem>
        ),
        cell: ({ row }) => {
          const { global_contribution: value } = row.original;
          if (value === undefined || value === null) return t('no-data');
          const formattedValue = cellFormatter.percentage(locale, value, {
            displayPercentageSign: false,
            displayZeroValue: false,
          });
          return <span className="text-xs">{t('percentage', { percentage: formattedValue })}</span>;
        },
      },
    ];
  }, [locale, environment, t, tooltips, searchParams, filters, onChangeFilters, filtersOptions]);

  return columns;
};

export const useData = (
  locationCode: string,
  environment: 'marine' | 'terrestrial' | null,
  sorting: SortingState,
  filters: Record<string, string[]>,
  pagination: PaginationState
) => {
  const locale = useLocale();
  const [customRegionLocations] = useSyncCustomRegion();

  // TODO TECH-3174: Clean up,
  const areTerritoriesActive = useFeatureFlag('are_territories_active');

  // TODO TECH-3174: Clean up, only filter by group code === locationCode
  const regionLocationFilter = useMemo(() => {
    if (areTerritoriesActive) {
      return {
        groups: {
          code: {
            $eq: locationCode,
          },
        },
      };
    }

    return {
      $and: [
        {
          groups: {
            code: {
              $eq: locationCode,
            },
          },
        },
        {
          code: {
            $notIn: [...NEW_LOCS],
          },
        },
      ],
    };
  }, [areTerritoriesActive, locationCode]);

  const customRegionLocationFilter = useMemo(() => {
    return {
      code: {
        $in: customRegionLocations?.size ? [...customRegionLocations] : [''],
      },
    };
  }, [customRegionLocations]);

  const {
    data: locationType,
    isSuccess: isLocationSuccess,
    isLoading: isLocationLoading,
    isFetching: isLocationFetching,
  } = useGetLocations<string>(
    {
      locale,
      // @ts-ignore
      fields: ['type'],
      filters: {
        code: locationCode,
      },
    },
    {
      query: {
        select: ({ data }) => data[0]?.attributes.type,
      },
    }
  );

  // By default, we always sort by location
  let sort = 'location.name:asc,environment.name:asc';
  if (sorting.length > 0) {
    sort = `${sorting[0].id}:${sorting[0].desc ? 'desc' : 'asc'}`;

    // In addition to sorting by the column the user asked about, we'll also always sort by
    // environment
    if (sorting[0].id !== 'environment.name') {
      sort = `${sort},environment.name:asc`;
    }
  }

  const { data, isLoading, isFetching } = useGetProtectionCoverageStats<
    [GlobalRegionalTableColumns[], ProtectionCoverageStatListResponseMetaPagination]
  >(
    {
      // @ts-ignore
      fields: ['coverage', 'protected_area', 'pas', 'oecms', 'global_contribution'],
      // @ts-ignore
      populate: {
        location: {
          fields: ['name', 'name_es', 'name_fr', 'code'],
          populate: {
            ...(environment === 'marine'
              ? {
                  mpaa_protection_level_stats: {
                    fields: ['percentage'],
                  },
                }
              : {}),
          },
        },
        environment: {
          fields: ['slug', 'name', 'locale'],
          populate: {
            localizations: {
              fields: ['name', 'locale'],
            },
          },
        },
      },
      filters: {
        ...(environment
          ? {
              environment: {
                slug: {
                  $eq: environment,
                },
              },
            }
          : {}),
        location: {
          ...(locationType === 'region'
            ? regionLocationFilter
            : locationType === 'custom_region'
              ? customRegionLocationFilter
              : {
                  type: {
                    $in: ['country', 'highseas'],
                  },
                }),
        },
        is_last_year: {
          $eq: true,
        },
        ...Object.entries(filters).reduce((res, [key, values]) => {
          if (!values || values.length === 0) {
            return res;
          }

          const reversePathItems = key.split('.').reverse();

          return reversePathItems.reduce((res, pathItem, index) => {
            if (index === 0) {
              return { [pathItem]: { $in: values } };
            }

            return { [pathItem]: res };
          }, {});
        }, {}),
      },
      'pagination[pageSize]': pagination.pageSize,
      'pagination[page]': pagination.pageIndex + 1,
      sort,
    },
    {
      query: {
        enabled: isLocationSuccess,
        placeholderData: [],
        keepPreviousData: true,
        select: (data) => {
          return [
            data.data?.map(({ attributes }): GlobalRegionalTableColumns => {
              const location = attributes.location?.data.attributes;
              const environment = attributes.environment?.data.attributes;

              const localizedEnvironment = [
                environment,
                ...(environment.localizations.data.map((environment) => environment.attributes) ??
                  []),
              ].find((data) => data.locale === locale);

              return {
                location: {
                  name: location?.name,
                  name_es: location?.name_es,
                  name_fr: location?.name_fr,
                  code: location.code,
                  mpaa_protection_level_stats: {
                    percentage: location?.mpaa_protection_level_stats?.data?.attributes.percentage,
                  },
                },
                environment: {
                  name: localizedEnvironment.name,
                  slug: localizedEnvironment.slug,
                },
                coverage: attributes.coverage,
                protected_area: attributes.protected_area,
                pas: attributes.pas,
                oecms: attributes.oecms,
                global_contribution: attributes.global_contribution,
              };
            }) ?? [],
            data.meta?.pagination ?? {},
          ];
        },
      },
    }
  );

  return {
    data,
    isLoading: isLoading || isLocationLoading,
    isFetching: isFetching || isLocationFetching,
  };
};
