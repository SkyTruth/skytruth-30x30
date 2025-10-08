import { useMemo } from 'react';

import { sortBy } from 'lodash-es';
import { useLocale } from 'next-intl';

import { formatPercentage, formatKM } from '@/lib/utils/formats';
import { useGetProtectionCoverageStats } from '@/types/generated/protection-coverage-stat';
import { ProtectionCoverageStatListResponseDataItem } from '@/types/generated/strapi.schemas';

import useNameField from '@/hooks/use-name-field';

export type FormattedStat = {
  location: string;
  iso: string;
  percentage: string;
  protectedArea: number;
  totalArea: number;
};

const useFormattedStats = (
  locationCodes: string[],
  environment: string,
  enabled: boolean
): [formattedStats: FormattedStat[], isFetching: boolean] => {
  const locale = useLocale();

  const DEFAULT_VALUE = '-';

  const nameField = useNameField();

  const { data: protectionCoverageStats, isFetching } = useGetProtectionCoverageStats<
    ProtectionCoverageStatListResponseDataItem[]
  >(
    {
      locale,
      filters: {
        location: {
          code: {
            $in: locationCodes,
          },
        },
        is_last_year: {
          $eq: true,
        },
        environment: {
          slug: {
            $eq: environment,
          },
        },
      },
      // @ts-expect-error
      populate: {
        location: {
          fields: [
            nameField,
            'code',
            'total_marine_area',
            'total_terrestrial_area',
            'has_shared_marine_area',
          ],
        },
      },
      // @ts-expect-error
      fields: ['coverage', 'protected_area', 'total_area'],
      'pagination[limit]': 1,
    },
    {
      query: {
        select: ({ data }) => data,
        enabled,
      },
    }
  );

  const formattedStats = useMemo(() => {
    if (protectionCoverageStats?.length > 0) {
      const stats = protectionCoverageStats.map((item, idx) => {
        const iso = item?.attributes?.location?.data?.attributes?.['code'] ?? locationCodes[idx];
        const location = item?.attributes?.location?.data?.attributes?.[nameField ?? iso];
        const coverage = item?.attributes?.coverage;
        const percentage =
          coverage !== null && coverage !== undefined
            ? formatPercentage(locale, coverage, {
                displayPercentageSign: false,
              })
            : DEFAULT_VALUE;

        const pArea = item?.attributes?.protected_area;
        const protectedArea =
          pArea !== null && pArea !== undefined ? formatKM(locale, pArea) : DEFAULT_VALUE;

        const tArea =
          item?.attributes?.total_area ??
          item?.attributes?.location?.data?.attributes?.[
            environment === 'marine' ? 'total_marine_area' : 'total_terrestrial_area'
          ];

        const totalArea = !Number.isNaN(+tArea) ? +tArea : DEFAULT_VALUE;

        return {
          location,
          iso,
          percentage,
          protectedArea,
          totalArea,
        };
      });

      // Sort so that territories are listed above sovereignties
      return sortBy(stats, (stat) => locationCodes.indexOf(stat.iso));
    }
    return null;
  }, [environment, locale, locationCodes, nameField, protectionCoverageStats]);

  return [formattedStats, isFetching];
};

export default useFormattedStats;
