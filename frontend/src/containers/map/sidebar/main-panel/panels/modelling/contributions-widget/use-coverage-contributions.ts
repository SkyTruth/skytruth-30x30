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

import { useFhpAnalysis } from './use-fhp-contributions';

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
  // On the marine tab, also list locations the shape adds only fully/highly protected area to
  // (inside an MPA that isn't fully/highly protected)
  const { data: fhpData } = useFhpAnalysis(tab === 'marine');
  const fhpLocations = tab === 'marine' ? fhpData?.locations_area : undefined;
  // Every location in the coverage or fully/highly protected analysis
  const locationCodes = useMemo(
    () => [...new Set([...locationsArea, ...(fhpLocations ?? [])].map(({ code }) => code))],
    [locationsArea, fhpLocations]
  );
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
    const locationByCode = new Map(
      (coverageStats ?? []).map((stat) => [stat.location?.code, stat.location as Location])
    );

    // Coverage of every location with stats, plus global
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

    // One entry per intersected location that has coverage stats
    const locations = locationCodes
      // TECH-3764: Clean up
      .filter((code) => (isIhoActive || !seaCodes.has(code)) && coverageByCode.has(code))
      .map((code) => toSectionStats(code));

    // Regions and Seas includes Areas Beyond National Jurisdiction (ABNJ, the high seas)
    const isHighSeas = ({ location }: SectionStats) => location?.type === HIGH_SEAS_TYPE;
    const countries = locations.filter((stats) => !isHighSeas(stats));
    const regionsAndSeas = locations.filter(isHighSeas);

    // Global: the world's coverage plus the shape's added area summed across locations
    const global =
      locations.length && coverageByCode.has(GLOBAL_CODE) ? toSectionStats(GLOBAL_CODE) : null;

    return { countries, regionsAndSeas, global };
  }, [coverageStats, locationsArea, locationCodes, seaCodes, isIhoActive, tab]);

  return { countries, regionsAndSeas, global, seaCodes, isLoading: isInitialLoading };
};

export default useCoverageContributions;
