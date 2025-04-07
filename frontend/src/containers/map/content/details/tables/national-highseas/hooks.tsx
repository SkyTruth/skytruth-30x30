import { useCallback, useMemo } from 'react';

import { AccessorKeyColumnDef, PaginationState, SortingState } from '@tanstack/react-table';
import { useLocale, useTranslations } from 'next-intl';

import FiltersButton from '@/components/filters-button';
import ExpansionControls from '@/containers/map/content/details/table/expansion-controls';
import HeaderItem from '@/containers/map/content/details/table/header-item';
import { cellFormatter } from '@/containers/map/content/details/table/helpers';
import SortingButton from '@/containers/map/content/details/table/sorting-button';
import TooltipButton from '@/containers/map/content/details/table/tooltip-button';
import { useGetDataInfos } from '@/types/generated/data-info';
import { useGetDataSources } from '@/types/generated/data-source';
import { useGetEnvironments } from '@/types/generated/environment';
import { useGetMpaIucnCategories } from '@/types/generated/mpa-iucn-category';
import { useGetMpaaEstablishmentStages } from '@/types/generated/mpaa-establishment-stage';
import { useGetMpaaProtectionLevels } from '@/types/generated/mpaa-protection-level';
import { useGetPas } from '@/types/generated/pa';
import { useGetProtectionStatuses } from '@/types/generated/protection-status';
import {
  Pa,
  PaChildrenDataItemAttributes,
  PaListResponse,
  PaListResponseMetaPagination,
} from '@/types/generated/strapi.schemas';

interface NationalHighseasTableRow {
  name: string;
  coverage: number;
  area: number;
  environment: {
    name: string;
    slug: string;
  };
  data_source: {
    title: string;
    slug: string;
  };
  protection_status: {
    name: string;
    slug: string;
  };
  iucn_category: {
    name: string;
    slug: string;
  };
  mpaa_establishment_stage: {
    name: string;
    slug: string;
  };
  mpaa_protection_level: {
    name: string;
    slug: string;
  };
}

export type NationalHighseasTableColumns = NationalHighseasTableRow & {
  subRows?: NationalHighseasTableRow[];
};

const TOOLTIP_MAPPING = {
  protectedArea: 'name-pa',
  coverage: 'coverage-wdpa',
  protectedAreaType: 'protected-area-type',
  establishmentStage: 'establishment-stage',
  protectionLevel: 'protection-level',
  fishingProtectionLevel: 'fishing-protection-level',
  area: 'protected-area-mpa',
  dataSource: 'details-data-source',
  iucnCategory: 'details-iucn-category',
};

const useTooltips = () => {
  const locale = useLocale();

  const { data: dataInfo } = useGetDataInfos(
    {
      locale,
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

  // Sources are kept out of these tooltips because there is a source column in the table
  const tooltips: {
    [key: string]: {
      text: string;
    };
  } = {};

  Object.entries(TOOLTIP_MAPPING).map(([key, value]) => {
    const tooltip = dataInfo.find(({ attributes }) => attributes.slug === value)?.attributes;

    if (!tooltip) return;

    tooltips[key] = { text: tooltip?.content };
  });

  return tooltips;
};

const useFiltersOptions = () => {
  const locale = useLocale();

  const { data: environmentOptions } = useGetEnvironments<{ name: string; value: string }[]>(
    {
      locale,
      // eslint-disable-next-line @typescript-eslint/ban-ts-comment
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

  const { data: dataSourceOptions } = useGetDataSources<{ name: string; value: string }[]>(
    {
      locale, // eslint-disable-next-line @typescript-eslint/ban-ts-comment
      // @ts-ignore
      fields: ['title', 'slug'],
      'pagination[limit]': -1,
    },
    {
      query: {
        select: ({ data }) =>
          data
            .map((dataSource) => ({
              name: dataSource.attributes.title,
              value: dataSource.attributes.slug,
            }))
            .filter(({ value }) =>
              // ? Even though there are more data sources, we limit the display to these
              ['mpatlas', 'protected-planet']?.includes(value)
            ),
        placeholderData: { data: [] },
      },
    }
  );

  const { data: protectionStatusOptions } = useGetProtectionStatuses<
    { name: string; value: string }[]
  >(
    {
      locale, // eslint-disable-next-line @typescript-eslint/ban-ts-comment
      // @ts-ignore
      fields: ['name', 'slug'],
      'pagination[limit]': -1,
    },
    {
      query: {
        select: ({ data }) =>
          data.map((protectionStatus) => ({
            name: protectionStatus.attributes.name,
            value: protectionStatus.attributes.slug,
          })),
        placeholderData: { data: [] },
      },
    }
  );

  const { data: iucnCategoryOptions } = useGetMpaIucnCategories<{ name: string; value: string }[]>(
    {
      locale, // eslint-disable-next-line @typescript-eslint/ban-ts-comment
      // @ts-ignore
      fields: ['name', 'slug'],
      'pagination[limit]': -1,
    },
    {
      query: {
        select: ({ data }) =>
          data.map((iucnCategory) => ({
            name: iucnCategory.attributes.name,
            value: iucnCategory.attributes.slug,
          })),
        placeholderData: { data: [] },
      },
    }
  );

  const { data: mpaaEstablishmentStageOptions } = useGetMpaaEstablishmentStages<
    { name: string; value: string }[]
  >(
    {
      locale, // eslint-disable-next-line @typescript-eslint/ban-ts-comment
      // @ts-ignore
      fields: ['name', 'slug'],
      'pagination[limit]': -1,
    },
    {
      query: {
        select: ({ data }) =>
          data.map((mpaaEstablishmentStage) => ({
            name: mpaaEstablishmentStage.attributes.name,
            value: mpaaEstablishmentStage.attributes.slug,
          })),
        placeholderData: { data: [] },
      },
    }
  );

  const { data: mpaaProtectionLevelOptions } = useGetMpaaProtectionLevels<
    { name: string; value: string }[]
  >(
    {
      locale, // eslint-disable-next-line @typescript-eslint/ban-ts-comment
      // @ts-ignore
      fields: ['name', 'slug'],
      'pagination[limit]': -1,
    },
    {
      query: {
        select: ({ data }) =>
          data.reduce((acc, mpaaProtectionLevel) => {
            /**
             * The following levels are not valid mpaa protection levels and hence don't make
             * sense as filters. They are just used internally for aggregating protection stats
             */
            if (
              mpaaProtectionLevel.attributes.slug !== 'fully-highly-protected' &&
              mpaaProtectionLevel.attributes.slug !== 'less-protected-unknown') {
              acc.push({
                name: mpaaProtectionLevel.attributes.name,
                value: mpaaProtectionLevel.attributes.slug,
              })
            }
            return acc;
          }, []),
        placeholderData: { data: [] },
      },
    }
  );

  return {
    environment: environmentOptions,
    dataSource: dataSourceOptions,
    protectionStatus: protectionStatusOptions,
    iucnCategory: iucnCategoryOptions,
    mpaaEstablishmentStage: mpaaEstablishmentStageOptions,
    mpaaProtectionLevel: mpaaProtectionLevelOptions,
  };
};

export const useColumns = (
  environment: 'marine' | 'terrestrial' | null,
  filters: Record<string, string[]>,
  onChangeFilters: (newFilters: Record<string, string[]>) => void
) => {
  const t = useTranslations('containers.map');
  const locale = useLocale();

  const tooltips = useTooltips();

  const filtersOptions = useFiltersOptions();

  const columns: AccessorKeyColumnDef<NationalHighseasTableColumns>[] = useMemo(() => {
    return [
      {
        id: 'name',
        accessorKey: 'name',
        header: ({ column }) => (
          <HeaderItem className="ml-6">
            <SortingButton column={column} />
            {t('name')}
            <TooltipButton tooltip={tooltips?.protectedArea} />
          </HeaderItem>
        ),
        cell: ({ row }) => {
          const {
            original: { name },
          } = row;
          return (
            <ExpansionControls row={row}>
              <span className="font-semibold">{name}</span>
            </ExpansionControls>
          );
        },
        size: 300,
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
          if (value === undefined || value === null) return <>&mdash;</>;

          const formattedCoverage = cellFormatter.percentage(locale, value, {
            displayZeroValue: false,
            displayPercentageSign: false,
          });

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
        id: 'area',
        accessorKey: 'area',
        header: ({ column }) => (
          <HeaderItem>
            <SortingButton column={column} />
            {t('area')}
            <TooltipButton tooltip={tooltips?.area} />
          </HeaderItem>
        ),
        cell: ({ row }) => {
          const { area: value } = row.original;
          const formattedValue = cellFormatter.area(locale, value);
          return <span>{t('area-km2', { area: formattedValue })}</span>;
        },
      },
      {
        id: 'data_source.title',
        accessorKey: 'data_source.title',
        header: () => (
          <HeaderItem>
            {environment !== 'terrestrial' && (
              <FiltersButton
                field="data_source.slug"
                options={filtersOptions.dataSource}
                values={filters['data_source.slug'] ?? []}
                onChange={(field, values) => onChangeFilters({ ...filters, [field]: values })}
              />
            )}
            {t('data-source')}
            <TooltipButton tooltip={tooltips?.dataSource} />
          </HeaderItem>
        ),
        cell: ({ row }) => {
          const { data_source } = row.original;
          const formattedValue = data_source?.title || t('n-a');
          return <>{formattedValue}</>;
        },
      },
      {
        id: 'protection_status.name',
        accessorKey: 'protection_status.name',
        header: () => (
          <HeaderItem>
            <FiltersButton
              field="protection_status.slug"
              options={filtersOptions.protectionStatus}
              values={filters['protection_status.slug'] ?? []}
              onChange={(field, values) => onChangeFilters({ ...filters, [field]: values })}
            />
            {t('type')}
            <TooltipButton tooltip={tooltips?.protectedAreaType} />
          </HeaderItem>
        ),
        cell: ({ row }) => {
          const { protection_status } = row.original;
          const formattedValue = protection_status?.name ?? '-';
          return <>{formattedValue}</>;
        },
      },
      {
        id: 'iucn_category.name',
        accessorKey: 'iucn_category.name',
        header: () => (
          <HeaderItem>
            <FiltersButton
              field="iucn_category.slug"
              options={filtersOptions.iucnCategory}
              values={filters['iucn_category.slug'] ?? []}
              onChange={(field, values) => onChangeFilters({ ...filters, [field]: values })}
            />
            {t('iucn-category')}
            <TooltipButton tooltip={tooltips?.iucnCategory} />
          </HeaderItem>
        ),
        cell: ({ row }) => {
          const { iucn_category } = row.original;
          const formattedValue = iucn_category?.name || t('n-a');
          return <>{formattedValue}</>;
        },
      },
      ...(environment === 'marine'
        ? [
          {
            id: 'mpaa_establishment_stage.name',
            accessorKey: 'mpaa_establishment_stage.name',
            header: () => (
              <HeaderItem>
                <FiltersButton
                  field="mpaa_establishment_stage.slug"
                  options={filtersOptions.mpaaEstablishmentStage}
                  values={filters['mpaa_establishment_stage.slug'] ?? []}
                  onChange={(field, values) => onChangeFilters({ ...filters, [field]: values })}
                />
                {t('establishment-stage')}
                <TooltipButton tooltip={tooltips?.establishmentStage} />
              </HeaderItem>
            ),
            cell: ({ row }) => {
              const { mpaa_establishment_stage } = row.original;

              const hasSubRowWithValue =
                row.subRows.length > 0 &&
                row.subRows.some((row) => !!row.original.mpaa_establishment_stage);

              let fallbackValue = t('not-assessed');
              if (hasSubRowWithValue) {
                fallbackValue = '−';
              }

              const formattedValue = mpaa_establishment_stage.name ?? fallbackValue;
              return <>{formattedValue}</>;
            },
          },
        ]
        : []),
      ...(environment === 'marine'
        ? [
          {
            id: 'mpaa_protection_level.name',
            accessorKey: 'mpaa_protection_level.name',
            header: () => (
              <HeaderItem>
                <FiltersButton
                  field="mpaa_protection_level.slug"
                  options={filtersOptions.mpaaProtectionLevel}
                  values={filters['mpaa_protection_level.slug'] ?? []}
                  onChange={(field, values) => onChangeFilters({ ...filters, [field]: values })}
                />
                {t('protection-level')}
                <TooltipButton tooltip={tooltips?.protectionLevel} />
              </HeaderItem>
            ),
            cell: ({ row }) => {
              const { mpaa_protection_level } = row.original;

              const hasSubRowWithValue =
                row.subRows.length > 0 &&
                row.subRows.some((row) => !!row.original.mpaa_protection_level);

              let fallbackValue = t('not-assessed');
              if (hasSubRowWithValue) {
                fallbackValue = '−';
              }

              const formattedValue = mpaa_protection_level.name ?? fallbackValue;
              return <>{formattedValue}</>;
            },
          },
        ]
        : []),
    ];
  }, [locale, environment, t, tooltips, filters, onChangeFilters, filtersOptions]);

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

  const queryFields = useMemo(() => ['name', 'coverage', 'area'], []);

  const queryPopulate = useMemo(
    () => ({
      environment: {
        fields: ['slug', 'name', 'locale'],
        populate: {
          localizations: {
            fields: ['name', 'locale'],
          },
        },
      },
      data_source: {
        fields: ['slug', 'title', 'locale'],
        populate: {
          localizations: {
            fields: ['slug', 'title', 'locale'],
          },
        },
      },
      protection_status: {
        fields: ['slug', 'name', 'locale'],
        populate: {
          localizations: {
            fields: ['slug', 'name', 'locale'],
          },
        },
      },
      iucn_category: {
        fields: ['slug', 'name', 'locale'],
        populate: {
          localizations: {
            fields: ['slug', 'name', 'locale'],
          },
        },
      },
      ...(environment === 'marine'
        ? {
          mpaa_establishment_stage: {
            fields: ['slug', 'name', 'locale'],
            populate: {
              localizations: {
                fields: ['slug', 'name', 'locale'],
              },
            },
          },
        }
        : {}),
      ...(environment === 'marine'
        ? {
          mpaa_protection_level: {
            fields: ['slug', 'name', 'locale'],
            populate: {
              localizations: {
                fields: ['slug', 'name', 'locale'],
              },
            },
          },
        }
        : {}),
    }),
    [environment]
  );

  const querySort = useMemo(() => {
    // By default, we always sort by protected area name
    let res = 'name:asc,environment.name:asc';
    if (sorting.length > 0) {
      res = `${sorting[0].id}:${sorting[0].desc ? 'desc' : 'asc'}`;

      // In addition to sorting by the column the user asked about, we'll also always sort by
      // environment
      if (sorting[0].id !== 'environment.name') {
        res = `${res},environment.name:asc`;
      }
    }

    return res;
  }, [sorting]);

  const queryFilters = useMemo(
    () => ({
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
        code: {
          $eq: locationCode,
        },
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
    }),
    [environment, filters, locationCode]
  );

  const isFiltering = useMemo(
    () =>
      Object.values(filters)
        .filter(Boolean)
        .some((value) => value.length > 0),
    [filters]
  );

  const processData = useCallback(
    (data: PaListResponse) => {
      return [
        data.data?.map(({ attributes }): NationalHighseasTableColumns => {
          const getData = (pa: Pa | PaChildrenDataItemAttributes) => {
            const environment = pa.environment?.data?.attributes;
            const localizedEnvironment = [
              environment,
              ...(environment?.localizations.data.map((environment) => environment.attributes) ??
                []),
            ].find((data) => data?.locale === locale);

            const dataSource = pa.data_source?.data?.attributes;
            const localizedDataSource = [
              dataSource,
              ...(dataSource?.localizations.data.map((dataSource) => dataSource.attributes) ?? []),
            ].find((data) => data?.locale === locale);

            const protectionStatus = pa.protection_status?.data?.attributes;
            const localizedProtectionStatus = [
              protectionStatus,
              ...(protectionStatus?.localizations.data.map(
                (protectionStatus) => protectionStatus.attributes
              ) ?? []),
            ].find((data) => data?.locale === locale);

            const iucnCategory = pa.iucn_category?.data?.attributes;
            const localizedIucnCategory = [
              iucnCategory,
              ...(iucnCategory?.localizations.data.map((iucnCategory) => iucnCategory.attributes) ??
                []),
            ].find((data) => data?.locale === locale);

            const mpaaEstablishmentStage = pa.mpaa_establishment_stage?.data?.attributes;
            const localizedMpaaEstablishmentStage = [
              mpaaEstablishmentStage,
              ...(mpaaEstablishmentStage?.localizations.data.map(
                (mpaaEstablishmentStage) => mpaaEstablishmentStage.attributes
              ) ?? []),
            ].find((data) => data?.locale === locale);

            const mpaaProtectionLevel = pa.mpaa_protection_level?.data?.attributes;
            const localizedMpaaProtectionLevel = [
              mpaaProtectionLevel,
              ...(mpaaProtectionLevel?.localizations.data.map(
                (mpaaProtectionLevel) => mpaaProtectionLevel.attributes
              ) ?? []),
            ].find((data) => data?.locale === locale);

            return {
              name: pa.name,
              coverage: pa.coverage,
              area: pa.area,
              environment: {
                name: localizedEnvironment?.name,
                slug: localizedEnvironment?.slug,
              },
              data_source: {
                title: localizedDataSource?.title,
                slug: localizedDataSource?.slug,
              },
              protection_status: {
                name: localizedProtectionStatus?.name,
                slug: localizedProtectionStatus?.slug,
              },
              iucn_category: {
                name: localizedIucnCategory?.name,
                slug: localizedIucnCategory?.slug,
              },
              mpaa_establishment_stage: {
                name: localizedMpaaEstablishmentStage?.name,
                slug: localizedMpaaEstablishmentStage?.slug,
              },
              mpaa_protection_level: {
                name: localizedMpaaProtectionLevel?.name,
                slug: localizedMpaaProtectionLevel?.slug,
              },
            };
          };

          return {
            ...getData(attributes),
            ...(attributes.children.data.length > 0
              ? {
                subRows: attributes.children.data.map(({ attributes }) => getData(attributes)),
              }
              : {}),
          };
        }) ?? [],
        data.meta?.pagination ?? {},
      ];
    },
    [locale]
  );

  // If the user isn't filtering, only one request is sufficient to get all of the table's data
  const { data, isLoading, isFetching } = useGetPas<
    [NationalHighseasTableColumns[], PaListResponseMetaPagination]
  >(
    {
      // eslint-disable-next-line @typescript-eslint/ban-ts-comment
      // @ts-ignore
      fields: queryFields,
      // eslint-disable-next-line @typescript-eslint/ban-ts-comment
      // @ts-ignore
      populate: {
        ...queryPopulate,
        children: {
          fields: queryFields,
          populate: queryPopulate,
          filters: queryFilters,
          sort: querySort,
        },
      },
      filters: {
        ...queryFilters,
        parent: {
          name: {
            $null: true,
          },
        },
      },
      'pagination[pageSize]': pagination.pageSize,
      'pagination[page]': pagination.pageIndex + 1,
      sort: querySort,
      // This parameter makes sure Strapi retains the parent for which children match the filters
      // but make the request slower, so it is only added when necessary
      ...(isFiltering ? { 'keep-if-children-match': true } : {}),
    },
    {
      query: {
        placeholderData: [],
        keepPreviousData: true,
        select: processData,
      },
    }
  );

  return { data, isLoading, isFetching };
};
