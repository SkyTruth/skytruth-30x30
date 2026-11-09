import { useMemo } from 'react';

import { useLocale } from 'next-intl';

import { MARINE_HABITAT_CHART_COLORS } from '@/constants/habitat-chart-colors';
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

// Habitats cb_api can analyze, in the order the panel lists them
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

// The CMS's maximum page size, so no row is cut off when locations have several update years
const ALL_ROWS = 100_000;

/** One habitat row under "Habitat Protection" */
export type HabitatContribution = {
  slug: string;
  name: string;
  color: string;
  status: StatStatus;
  contribution?: Contribution;
};

/**
 * "Habitat Protection" stats for the Conservation Builder panel (marine only), keyed by
 * location code, with `GLOB` for the Global section. Lists only the habitats the drawn shape
 * adds protection to
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

  // Added habitat area per location, one request per habitat
  const analyses = useModellingStats(
    'habitats',
    HABITATS.map(({ slug }) => ({ habitat: slug })),
    { enabled }
  );

  // Existing protected habitat area and habitat extent per location
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
            $in: HABITATS.map(({ strapiSlug }) => strapiSlug),
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

    // Newest year per location and habitat
    const latestStats = new Map<string, HabitatStat>();
    stats.data.forEach((stat) => {
      const key = `${stat.location?.code}|${stat.habitat?.slug}`;
      if (!latestStats.has(key)) latestStats.set(key, stat);
    });

    HABITATS.forEach(({ slug, strapiSlug }, index) => {
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
        const contribution = contributions?.get(code);
        // Leave out habitats the shape adds no protection to
        if (contribution && contribution.added <= 0) return;

        rowsByCode.set(code, [
          ...(rowsByCode.get(code) ?? []),
          {
            slug,
            name: habitatNames?.[strapiSlug] ?? strapiSlug,
            color: MARINE_HABITAT_CHART_COLORS[strapiSlug],
            status: toStatus(analysis),
            contribution,
          },
        ]);
      });
    });

    return rowsByCode;
  }, [stats.data, analyses, codes, seaCodes, habitatNames]);

  return { habitatsByCode, status: toStatus(stats) };
};

export default useHabitatContributions;
