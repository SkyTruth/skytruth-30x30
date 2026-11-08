import { useMemo } from 'react';

import {
  Contribution,
  computeContribution,
  getAddedArea,
  sumAddedArea,
} from '@/lib/utils/modelling-contributions';
import { useGetMpaaProtectionLevelStats } from '@/types/generated/mpaa-protection-level-stat';
import { MpaaProtectionLevelStat } from '@/types/generated/strapi.schemas';

import { GLOBAL_CODE } from './use-coverage-contributions';
import useModellingStat from './use-modelling-stat';

const FHP_LEVEL = 'fully-highly-protected';

/**
 * "Fully/Highly Protected" stats for the Conservation Builder panel (marine only), keyed by
 * location code, with `GLOB` for the Global section
 *
 * The added area comes from cb_api's protection-level analysis of the drawn shape; the
 * existing fully/highly protected area and the total area come from Strapi's MPAA
 * protection level stats. A location without a Strapi row has no entry
 *
 * @param codes locations listed in the panel
 * @param seaCodes IHO seas, left out of the Global sum because they overlap national waters
 * @param enabled false on the terrestrial tab
 */
const useFhpContributions = (codes: string[], seaCodes: ReadonlySet<string>, enabled: boolean) => {
  // Added fully/highly protected area per location
  const {
    data: fhpData,
    isInitialLoading: isAnalysisLoading,
    isError,
  } = useModellingStat(
    'protection-level',
    { level: FHP_LEVEL, environment: 'marine' },
    { enabled }
  );

  // Existing fully/highly protected area per location, plus global
  const { data: fhpStats, isInitialLoading: isStatsLoading } = useGetMpaaProtectionLevelStats<
    MpaaProtectionLevelStat[]
  >(
    {
      filters: {
        location: {
          code: {
            $in: [...codes, GLOBAL_CODE],
          },
        },
        mpaa_protection_level: {
          slug: {
            $eq: FHP_LEVEL,
          },
        },
      },
      // @ts-ignore
      populate: {
        location: {
          fields: ['code'],
        },
      },
      // @ts-ignore
      fields: ['area', 'total_area'],
      'pagination[limit]': codes.length + 1,
    },
    {
      query: {
        enabled: enabled && codes.length > 0,
        select: ({ data }) => data ?? [],
        refetchOnWindowFocus: false,
      },
    }
  );

  const fhpByCode = useMemo(() => {
    const contributions = new Map<string, Contribution>();
    if (!fhpData || !fhpStats) return contributions;

    const addedByCode = new Map(
      fhpData.locations_area.map((locationArea) => [locationArea.code, getAddedArea(locationArea)])
    );

    fhpStats.forEach(({ location, area, total_area }) => {
      const code = location?.code;
      if (!code) return;

      const added =
        code === GLOBAL_CODE
          ? sumAddedArea(fhpData.locations_area, seaCodes)
          : (addedByCode.get(code) ?? 0);

      contributions.set(code, computeContribution(Number(area ?? 0), added, Number(total_area)));
    });

    return contributions;
  }, [fhpData, fhpStats, seaCodes]);

  return { fhpByCode, isLoading: isAnalysisLoading || isStatsLoading, isError };
};

export default useFhpContributions;
