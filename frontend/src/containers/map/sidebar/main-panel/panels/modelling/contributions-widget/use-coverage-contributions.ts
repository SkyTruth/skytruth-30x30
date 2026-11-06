import { useMemo } from 'react';

import { useAtomValue } from 'jotai';
import { useLocale } from 'next-intl';

import { modellingAtom } from '@/containers/map/store';
import { useSyncMapContentSettings } from '@/containers/map/sync-settings';
import { useFeatureFlag } from '@/hooks/use-feature-flag';
import {
  Contribution,
  computeContribution,
  getAddedArea,
  sumAddedArea,
} from '@/lib/utils/modelling-contributions';
import { useGetLocations } from '@/types/generated/location';
import { useGetProtectionCoverageStats } from '@/types/generated/protection-coverage-stat';
import { Location, ProtectionCoverageStat } from '@/types/generated/strapi.schemas';

export const GLOBAL_CODE = 'GLOB';
const HIGH_SEAS_TYPE = 'highseas';

/** Stats for one collapsible location in the Conservation Builder panel */
export type SectionStats = {
  code: string;
  location: Location;
  // "Marine/Terrestrial Conservation Coverage" block
  coverage: Contribution;
  // Coverage target in % for the current tab, as in the Progress Tracker; unset if none reported
  coverageTarget?: number;
};

// Same target fields the Progress Tracker's coverage widgets read
const getCoverageTarget = (location: Location, tab: string) =>
  (tab === 'marine' ? location?.marine_target : location?.terrestrial_target) ?? undefined;

/**
 * Coverage stats for the Conservation Builder panel, one entry per location the drawn shape
 * intersects, grouped by panel section (e.g. Countries, Global)
 *
 * The added area comes from the analysis result in modellingAtom; the existing protected
 * area and the total area come from Strapi's protection coverage stats
 */
const useCoverageContributions = () => {
  const locale = useLocale();
  const [{ tab }] = useSyncMapContentSettings();
  const { data: modellingData } = useAtomValue(modellingAtom);

  // TECH-3764: Clean up
  const isIhoActive = useFeatureFlag('is_iho_active');

  const locationsArea = useMemo(() => modellingData?.locations_area ?? [], [modellingData]);
  const locationCodes = useMemo(() => locationsArea.map(({ code }) => code), [locationsArea]);
  const enabled = locationCodes.length > 0 && ['marine', 'terrestrial'].includes(tab);

  // Latest coverage stats for every location the shape intersects, plus global
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
    const statsByCode = new Map(
      (coverageStats ?? []).map((stat) => [stat.location?.code, stat] as const)
    );

    // One entry per intersected location that has coverage stats
    const locations = locationsArea.flatMap((locationArea): SectionStats[] => {
      const { code } = locationArea;
      // TECH-3764: Clean up
      if (!isIhoActive && seaCodes.has(code)) return [];

      const stat = statsByCode.get(code);
      if (!stat) return [];

      const location = stat.location as Location;
      // Fallback area if the location isn't in WDPA
      const fallbackArea =
        tab === 'marine' ? location?.total_marine_area : location?.total_terrestrial_area;
      const total = Number(stat.total_area ?? fallbackArea);

      return [
        {
          code,
          location,
          coverage: computeContribution(
            stat.protected_area ?? 0,
            getAddedArea(locationArea),
            total
          ),
          coverageTarget: getCoverageTarget(location, tab),
        },
      ];
    });

    // Regions and Seas includes High Seas (ABNJ)
    const isHighSeas = ({ location }: SectionStats) => location?.type === HIGH_SEAS_TYPE;
    const countries = locations.filter((stats) => !isHighSeas(stats));
    const regionsAndSeas = locations.filter(isHighSeas);

    // Global: the world's coverage plus the shape's added area summed across locations
    const globalStat = statsByCode.get(GLOBAL_CODE);
    const global: SectionStats | null =
      globalStat && locations.length
        ? {
            code: GLOBAL_CODE,
            location: globalStat.location as Location,
            coverage: computeContribution(
              globalStat.protected_area ?? 0,
              sumAddedArea(locationsArea, seaCodes),
              Number(globalStat.total_area ?? 0)
            ),
            coverageTarget: getCoverageTarget(globalStat.location as Location, tab),
          }
        : null;

    return { countries, regionsAndSeas, global };
  }, [coverageStats, locationsArea, seaCodes, isIhoActive, tab]);

  return { countries, regionsAndSeas, global, isLoading: isInitialLoading };
};

export default useCoverageContributions;
