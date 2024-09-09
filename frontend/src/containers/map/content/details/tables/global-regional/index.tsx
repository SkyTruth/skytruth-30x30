import { useMemo } from 'react';

import { useRouter } from 'next/router';

import { useLocale } from 'next-intl';

import TooltipButton from '@/components/tooltip-button';
import Table from '@/containers/map/content/details/table';
import useColumns from '@/containers/map/content/details/tables/global-regional/useColumns';
import { FCWithMessages } from '@/types';
import { useGetLocations } from '@/types/generated/location';
import type { LocationListResponseDataItem } from '@/types/generated/strapi.schemas';

import SortingButton from '../../table/sorting-button';

const GlobalRegionalTable: FCWithMessages = () => {
  const {
    query: { locationCode = 'GLOB' },
  } = useRouter();
  const locale = useLocale();

  const globalLocationQuery = useGetLocations(
    {
      locale,
      filters: {
        code: 'GLOB',
      },
    },
    {
      query: {
        select: ({ data }) => data?.[0]?.attributes,
      },
    }
  );

  const locationsQuery = useGetLocations(
    {
      locale,
      filters: {
        code: locationCode,
      },
    },
    {
      query: {
        queryKey: ['locations', locationCode],
        select: ({ data }) => data?.[0]?.attributes,
      },
    }
  );

  const columns = useColumns();

  // Get location data and calculate data to display on the table
  const { data: locationsData }: { data: LocationListResponseDataItem[] } = useGetLocations(
    {
      // We will use the data from the `localizations` field because the models “Protection Coverage
      // Stats” and “Mpaa Protection Level Stats” are not localised and their relationship to the
      // “Location” model only points to a specific localised version. As such, we're forced to load
      // all the locales of the “Location” model and then figure out which version has the relation
      // to the other model.
      locale: 'en',
      filters:
        locationsQuery.data?.type === 'region'
          ? {
              groups: {
                code: {
                  $eq: locationsQuery.data?.code,
                },
              },
            }
          : {
              type: {
                $eq: ['country', 'highseas'],
              },
            },
      // eslint-disable-next-line @typescript-eslint/ban-ts-comment
      // @ts-ignore
      fields: ['code', 'name', 'type', 'totalMarineArea'],
      // eslint-disable-next-line @typescript-eslint/ban-ts-comment
      // @ts-ignore
      populate: {
        // This part if for the English version only
        protection_coverage_stats: {
          fields: ['cumSumProtectedArea', 'protectedAreasCount', 'year'],
          populate: {
            protection_status: {
              fields: ['slug', 'name'],
            },
          },
        },
        mpaa_protection_level_stats: {
          fields: ['area'],
          populate: {
            mpaa_protection_level: {
              fields: ['slug', 'name'],
            },
          },
        },
        // fishing_protection_level_stats: {
        //   fields: ['area'],
        //   populate: {
        //     fishing_protection_level: {
        //       fields: ['slug', 'name'],
        //     },
        //   },
        // },
        // This part is for the Spanish and French versions
        localizations: {
          fields: ['code', 'name', 'type', 'totalMarineArea', 'locale'],
          populate: {
            protection_coverage_stats: {
              fields: ['cumSumProtectedArea', 'protectedAreasCount', 'year'],
              populate: {
                protection_status: {
                  fields: ['slug', 'name'],
                },
              },
            },
            mpaa_protection_level_stats: {
              fields: ['area'],
              populate: {
                mpaa_protection_level: {
                  fields: ['slug', 'name'],
                },
              },
            },
            // fishing_protection_level_stats: {
            //   fields: ['area'],
            //   populate: {
            //     fishing_protection_level: {
            //       fields: ['slug', 'name'],
            //     },
            //   },
            // },
          },
        },
      },
      // populate: '*',
      'pagination[limit]': -1,
    },
    {
      query: {
        select: ({ data }) => data,
        placeholderData: { data: [] },
      },
    }
  );

  // Calculate table data
  const parsedData = useMemo(() => {
    return locationsData.map(({ attributes: location }) => {
      const localizedLocation = [
        { ...location, locale: 'en' },
        ...(location.localizations.data.map(
          // The types below are wrong. There is definitely an `attributes` key inside
          // `localizations`.
          // eslint-disable-next-line @typescript-eslint/ban-ts-comment
          // @ts-ignore
          (localization) => localization.attributes
        ) ?? []),
      ].find((data) => data.locale === locale);

      // Base stats needed for calculations
      const protectionCoverageStats =
        [
          location.protection_coverage_stats.data,
          ...(location.localizations.data.map(
            // The types below are wrong. There is definitely an `attributes` key inside
            // `localizations`.
            // eslint-disable-next-line @typescript-eslint/ban-ts-comment
            // @ts-ignore
            (localization) => localization.attributes.protection_coverage_stats.data
          ) ?? []),
        ].find((data) => data?.length) ?? [];

      const mpaaProtectionLevelStats =
        [
          location.mpaa_protection_level_stats.data,
          ...(location.localizations.data.map(
            // The types below are wrong. There is definitely an `attributes` key inside
            // `localizations`.
            // eslint-disable-next-line @typescript-eslint/ban-ts-comment
            // @ts-ignore
            (localization) => localization.attributes.mpaa_protection_level_stats.data
          ) ?? []),
        ].find((data) => data?.length) ?? [];

      // const fishingProtectionLevelStats =
      //   [
      //     location.fishing_protection_level_stats.data,
      //     ...(location.localizations.data.map(
      //       // The types below are wrong. There is definitely an `attributes` key inside
      //       // `localizations`.
      //       // eslint-disable-next-line @typescript-eslint/ban-ts-comment
      //       // @ts-ignore
      //       (localization) => localization.attributes.fishing_protection_level_stats.data
      //     ) ?? []),
      //   ].find((data) => data?.length) ?? [];

      // Find coverage stats data for the last available year in the data
      const lastCoverageDataYear = Math.max(
        ...protectionCoverageStats.map(({ attributes }) => attributes.year)
      );
      const coverageStats = protectionCoverageStats.filter(
        ({ attributes }) => attributes.year === lastCoverageDataYear
      );

      // Coverage calculations (MPA + OECM)
      const protectedArea = coverageStats.reduce(
        (acc, { attributes }) => acc + attributes?.cumSumProtectedArea,
        0
      );
      const coveragePercentage = (protectedArea * 100) / location.totalMarineArea;

      // MPAs calculations
      const numMPAs =
        coverageStats.find(
          ({ attributes }) => attributes?.protection_status?.data?.attributes?.slug === 'mpa'
        )?.attributes?.protectedAreasCount || 0;

      // OECMs calculations
      const numOECMs =
        coverageStats.find(
          ({ attributes }) => attributes?.protection_status?.data?.attributes?.slug === 'oecm'
        )?.attributes?.protectedAreasCount || 0;

      const percentageMPAs = (numMPAs * 100) / (numMPAs + numOECMs);
      const percentageOECMs = (numOECMs * 100) / (numMPAs + numOECMs);

      // Fully/Highly Protected calculations
      const fullyHighlyProtected = mpaaProtectionLevelStats.filter(
        ({ attributes }) =>
          attributes?.mpaa_protection_level?.data?.attributes?.slug === 'fully-highly-protected'
      );
      const fullyHighlyProtectedArea = fullyHighlyProtected.reduce(
        (acc, { attributes }) => acc + attributes?.area,
        0
      );
      const fullyHighlyProtectedAreaPercentage =
        (fullyHighlyProtectedArea * 100) / location.totalMarineArea;

      // Highly Protected LFP calculations
      // const lfpHighProtected = fishingProtectionLevelStats.filter(
      //   ({ attributes }) =>
      //     attributes?.fishing_protection_level?.data?.attributes?.slug === 'highly'
      // );
      // const lfpHighProtectedArea = lfpHighProtected.reduce(
      //   (acc, { attributes }) => acc + attributes?.area,
      //   0
      // );
      // const lfpHighProtectedPercentage = (lfpHighProtectedArea * 100) / location.totalMarineArea;

      // Global contributions calculations
      const globalContributionPercentage =
        (protectedArea * 100) / globalLocationQuery?.data?.totalMarineArea;

      return {
        location: localizedLocation.name,
        locationCode: location.code,
        coverage: coveragePercentage,
        area: protectedArea,
        locationType: location.type,
        mpas: percentageMPAs,
        oecms: percentageOECMs,
        fullyHighlyProtected: fullyHighlyProtectedAreaPercentage,
        // highlyProtectedLfp: lfpHighProtectedPercentage,
        globalContribution: globalContributionPercentage,
      };
    });
  }, [locale, globalLocationQuery?.data, locationsData]);

  const tableData = parsedData;

  // eslint-disable-next-line @typescript-eslint/ban-ts-comment
  //@ts-ignore
  return <Table columns={columns} data={tableData} />;
};

GlobalRegionalTable.messages = [
  'containers.map',
  ...Table.messages,
  // Dependencies of `useColumns`
  ...SortingButton.messages,
  ...TooltipButton.messages,
];

export default GlobalRegionalTable;
