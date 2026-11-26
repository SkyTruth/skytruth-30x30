import { useMemo } from 'react';

import { useAtomValue } from 'jotai';
import { useLocale } from 'next-intl';

import { modellingAtom } from '@/containers/map/store';
import { useSyncMapContentSettings } from '@/containers/map/sync-settings';
import { useFeatureFlag } from '@/hooks/use-feature-flag';
import { Contribution, GLOBAL_CODE, buildContributions } from '@/lib/utils/modelling-contributions';
import { useGetLocations } from '@/types/generated/location';
import { useGetProtectionCoverageStats } from '@/types/generated/protection-coverage-stat';
import { Location, ProtectionCoverageStat } from '@/types/generated/strapi.schemas';

const HIGH_SEAS_TYPE = 'highseas';

export type SectionStats = {
  code: string;
  location: Location;
  coverage: Contribution;
  coverageTarget?: number;
};

const getCoverageTarget = (location: Location, tab: string) =>
  (tab === 'marine' ? location?.marine_target : location?.terrestrial_target) ?? undefined;

const useCoverageContributions = () => {
  const locale = useLocale();
  const [{ tab }] = useSyncMapContentSettings();
  const { data: modellingData } = useAtomValue(modellingAtom);

  // TECH-3764: Clean up
  const isIhoActive = useFeatureFlag('is_iho_active');

  const locationsArea = useMemo(() => modellingData?.locations_area ?? [], [modellingData]);
  const locationCodes = useMemo(() => locationsArea.map(({ code }) => code), [locationsArea]);
  const enabled = locationCodes.length > 0 && ['marine', 'terrestrial'].includes(tab);

  const { data: coverageStats, isInitialLoading } = useGetProtectionCoverageStats<
    ProtectionCoverageStat[]
  >(
    {
      locale,
      filters: {
        location: {
          code: {
            $in: [...locationCodes, GLOBAL_CODE],
          },
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
            'code',
            'type',
            'total_marine_area',
            'total_terrestrial_area',
            'marine_target',
            'terrestrial_target',
          ],
        },
      },
      'pagination[limit]': locationCodes.length + 1,
      // @ts-ignore
      fields: ['protected_area', 'total_area'],
    },
    {
      query: {
        enabled,
        select: ({ data }) => data ?? [],
        refetchOnWindowFocus: false,
      },
    }
  );

  // Exclude seas from the contributions because they overlap national waters
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

  const { countries, regionsAndSeas, global } = useMemo(() => {
    const locationByCode = new Map(
      (coverageStats ?? []).map((stat) => [stat.location?.code, stat.location as Location])
    );

    const coverageByCode = buildContributions(
      (coverageStats ?? []).map(({ location, protected_area, total_area }) => ({
        code: location?.code,
        existing: protected_area ?? 0,
        // Fallback area if the location isn't in WDPA
        total: Number(
          total_area ??
            (tab === 'marine' ? location?.total_marine_area : location?.total_terrestrial_area)
        ),
      })),
      locationsArea,
      seaCodes
    );

    const toSectionStats = (code: string): SectionStats => {
      const location = locationByCode.get(code);
      return {
        code,
        location,
        coverage: coverageByCode.get(code),
        coverageTarget: getCoverageTarget(location, tab),
      };
    };

    const locations = locationsArea
      // TECH-3764: Clean up
      .filter(({ code }) => (isIhoActive || !seaCodes.has(code)) && coverageByCode.has(code))
      .map(({ code }) => toSectionStats(code));

    // Regions and Seas includes Areas Beyond National Jurisdiction (ABNJ, the high seas)
    const isHighSeas = ({ location }: SectionStats) => location?.type === HIGH_SEAS_TYPE;
    const countries = locations.filter((stats) => !isHighSeas(stats));
    const regionsAndSeas = locations.filter(isHighSeas);

    const global =
      locations.length > 0 && coverageByCode.has(GLOBAL_CODE) ? toSectionStats(GLOBAL_CODE) : null;

    return { countries, regionsAndSeas, global };
  }, [coverageStats, locationsArea, seaCodes, isIhoActive, tab]);

  return { countries, regionsAndSeas, global, isLoading: isInitialLoading };
};

export default useCoverageContributions;
