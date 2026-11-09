import { useMemo } from 'react';

import { useLocale } from 'next-intl';

import { MARINE_HABITAT_CHART_COLORS } from '@/constants/habitat-chart-colors';
import { useFeatureFlag } from '@/hooks/use-feature-flag';
import {
  Baseline,
  Contribution,
  GLOBAL_CODE,
  buildContributions,
} from '@/lib/utils/modelling-contributions';
import { useGetHabitats } from '@/types/generated/habitat';
import { useGetHabitatStats } from '@/types/generated/habitat-stat';
import { HabitatStat } from '@/types/generated/strapi.schemas';

import { StatStatus, toStatus } from './stat-status';
import { useModellingStats } from './use-modelling-stat';

// Habitats cb_api can analyze, in the order the panel lists them (same as the details panel).
// `strapiSlug` is the habitat's slug in Strapi and in MARINE_HABITAT_CHART_COLORS
const HABITATS = [
  { slug: 'climate-resilient-corals', strapiSlug: 'climate-resilient-corals' },
  { slug: 'other-corals', strapiSlug: 'other-corals' },
  { slug: 'cold-water-corals', strapiSlug: 'cold-water corals' },
  { slug: 'mangroves', strapiSlug: 'mangroves' },
  { slug: 'seagrasses', strapiSlug: 'seagrasses' },
  { slug: 'saltmarshes', strapiSlug: 'saltmarshes' },
  { slug: 'seamounts', strapiSlug: 'seamounts' },
];

const CLIMATE_RESILIENT_CORALS_SLUGS = ['climate-resilient-corals', 'other-corals'];

// The CMS's maximum page size, so every year of every requested row comes back
const ALL_ROWS = 100_000;

/** One habitat row under "Habitat Protection" */
export type HabitatContribution = {
  slug: string;
  name: string;
  color: string;
  // State of this habitat's analysis request
  status: StatStatus;
  contribution?: Contribution;
};

/**
 * "Habitat Protection" stats for the Conservation Builder panel (marine only), keyed by
 * location code, with `GLOB` for the Global section
 *
 * The added area comes from one cb_api habitats analysis per habitat; the existing protected
 * area and the habitat's extent come from Strapi's habitat stats, newest year per location
 * and habitat. A habitat with no extent in a location is left out of that location
 *
 * @param codes locations listed in the panel
 * @param seaCodes IHO seas, left out of the Global sum because they overlap national waters
 * @param enabled false on the terrestrial tab
 */
const useHabitatContributions = (
  codes: string[],
  seaCodes: ReadonlySet<string>,
  enabled: boolean
) => {
  const locale = useLocale();

  // TECH-3472: remove feature flag (climate resilient corals)
  const isClimateResCoralsActive = useFeatureFlag('is_climate_res_corals_active');
  const habitats = useMemo(
    () =>
      HABITATS.filter(
        ({ slug }) => isClimateResCoralsActive || !CLIMATE_RESILIENT_CORALS_SLUGS.includes(slug)
      ),
    [isClimateResCoralsActive]
  );

  // Added habitat area per location, one request per habitat
  const analyses = useModellingStats(
    'habitats',
    habitats.map(({ slug }) => ({ habitat: slug })),
    { enabled }
  );

  // Existing protected habitat area and habitat extent per location, every year
  const stats = useGetHabitatStats<HabitatStat[]>(
    {
      filters: {
        location: {
          code: {
            $in: [...codes, GLOBAL_CODE],
          },
        },
        environment: {
          slug: {
            $eq: 'marine',
          },
        },
        habitat: {
          slug: {
            $in: habitats.map(({ strapiSlug }) => strapiSlug),
          },
        },
      },
      // @ts-ignore
      populate: {
        location: {
          fields: ['code'],
        },
        habitat: {
          fields: ['slug'],
        },
      },
      // @ts-ignore
      fields: ['year', 'protected_area', 'total_area'],
      sort: 'year:desc',
      'pagination[limit]': ALL_ROWS,
    },
    {
      query: {
        enabled: enabled && codes.length > 0,
        select: ({ data }) => data ?? [],
        refetchOnWindowFocus: false,
      },
    }
  );

  // Habitat names in the current language
  const { data: habitatNames } = useGetHabitats<Record<string, string>>(
    {
      locale,
      // @ts-ignore
      fields: ['slug', 'name'],
    },
    {
      query: {
        enabled,
        select: ({ data }) => Object.fromEntries(data.map(({ slug, name }) => [slug, name])),
      },
    }
  );

  const habitatsByCode = useMemo(() => {
    const rowsByCode = new Map<string, HabitatContribution[]>();
    if (!stats.data) return rowsByCode;

    // Newest year per location and habitat (rows come newest first)
    const latestStats = new Map<string, HabitatStat>();
    stats.data.forEach((stat) => {
      const key = `${stat.location?.code}|${stat.habitat?.slug}`;
      if (!latestStats.has(key)) latestStats.set(key, stat);
    });

    habitats.forEach(({ slug, strapiSlug }, index) => {
      const analysis = analyses[index];

      // Locations where the habitat exists
      const baselines = [...codes, GLOBAL_CODE].flatMap((code): Baseline[] => {
        const stat = latestStats.get(`${code}|${strapiSlug}`);
        return Number(stat?.total_area)
          ? [{ code, existing: Number(stat.protected_area), total: Number(stat.total_area) }]
          : [];
      });
      const contributions = analysis.data
        ? buildContributions(baselines, analysis.data.locations_area, seaCodes)
        : undefined;

      baselines.forEach(({ code }) => {
        rowsByCode.set(code, [
          ...(rowsByCode.get(code) ?? []),
          {
            slug,
            name: habitatNames?.[strapiSlug] ?? strapiSlug,
            color: MARINE_HABITAT_CHART_COLORS[strapiSlug],
            status: toStatus(analysis),
            contribution: contributions?.get(code),
          },
        ]);
      });
    });

    return rowsByCode;
  }, [stats.data, habitats, analyses, codes, seaCodes, habitatNames]);

  return { habitatsByCode, status: toStatus(stats) };
};

export default useHabitatContributions;
