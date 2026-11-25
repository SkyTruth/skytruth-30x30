import { useMemo } from 'react';

import { useLocale } from 'next-intl';

import {
  MARINE_HABITAT_CHART_COLORS,
  TERRESTRIAL_HABITAT_CHART_COLORS,
} from '@/constants/habitat-chart-colors';
import useDataInfoTooltips, { DataInfoTooltip } from '@/hooks/use-data-info-tooltips';
import { useModellingStats } from '@/hooks/use-modelling-stat';
import {
  Baseline,
  Contribution,
  GLOBAL_CODE,
  buildContributions,
} from '@/lib/utils/modelling-contributions';
import { useGetHabitats } from '@/types/generated/habitat';
import { useGetHabitatStats } from '@/types/generated/habitat-stat';
import { HabitatStat } from '@/types/generated/strapi.schemas';

import { StatStatus, toStatus } from './helpers';

export type HabitatEnvironment = 'marine' | 'terrestrial';

type HabitatConfig = {
  // The habitat's slug in cb_api's response
  slug: string;
  // The habitat's slug in Strapi and in the habitat chart colors
  strapiSlug: string;
  // The `habitat` sent to cb_api's /habitats to get this habitat
  request: string;
};

const HABITATS: Record<HabitatEnvironment, HabitatConfig[]> = {
  marine: [
    { slug: 'climate-resilient-corals', strapiSlug: 'climate-resilient-corals' },
    { slug: 'other-corals', strapiSlug: 'other-corals' },
    { slug: 'cold-water-corals', strapiSlug: 'cold-water corals' },
    { slug: 'mangroves', strapiSlug: 'mangroves' },
    { slug: 'seagrasses', strapiSlug: 'seagrasses' },
    { slug: 'saltmarshes', strapiSlug: 'saltmarshes' },
    { slug: 'seamounts', strapiSlug: 'seamounts' },
  ].map((habitat) => ({ ...habitat, request: habitat.slug })),
  terrestrial: Object.keys(TERRESTRIAL_HABITAT_CHART_COLORS).map((slug) => ({
    slug,
    strapiSlug: slug,
    request: 'terrestrial-habitats',
  })),
};

const toRequests = (habitats: HabitatConfig[]) =>
  [...new Set(habitats.map(({ request }) => request))].map((habitat) => ({ habitat }));

const HABITAT_REQUESTS: Record<HabitatEnvironment, { habitat: string }[]> = {
  marine: toRequests(HABITATS.marine),
  terrestrial: toRequests(HABITATS.terrestrial),
};

const HABITAT_COLORS: Record<HabitatEnvironment, Record<string, string>> = {
  marine: MARINE_HABITAT_CHART_COLORS,
  terrestrial: TERRESTRIAL_HABITAT_CHART_COLORS,
};

// Terrestrial habitats come from one source, so they share a tooltip at the top
const TERRESTRIAL_TOOLTIP_SLUG = 'habitat-widget-terrestrial';

// The CMS's maximum page size, so no row is cut off when locations have several update years
const ALL_ROWS = 100_000;

export type HabitatContribution = {
  slug: string;
  name: string;
  color: string;
  status: StatStatus;
  contribution?: Contribution;
  // Marine only
  tooltip?: DataInfoTooltip;
};

const useHabitatContributions = (
  codes: string[],
  seaCodes: ReadonlySet<string>,
  environment: HabitatEnvironment
) => {
  const locale = useLocale();
  const habitats = HABITATS[environment];
  const requests = HABITAT_REQUESTS[environment];
  const strapiSlugs = useMemo(() => habitats.map(({ strapiSlug }) => strapiSlug), [habitats]);

  const analyses = useModellingStats('habitats', requests);

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
            $eq: environment,
          },
        },
        habitat: {
          slug: {
            $in: strapiSlugs,
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
        enabled: codes.length > 0,
        select: ({ data }) => data ?? [],
        refetchOnWindowFocus: false,
      },
    }
  );

  const { data: habitatNames } = useGetHabitats<Record<string, string>>(
    {
      locale,
      // @ts-ignore
      fields: ['slug', 'name'],
      filters: {
        slug: {
          $in: strapiSlugs,
        },
      },
    },
    {
      query: {
        select: ({ data }) => Object.fromEntries(data.map(({ slug, name }) => [slug, name])),
      },
    }
  );

  const tooltips = useDataInfoTooltips(
    environment === 'marine' ? strapiSlugs : [TERRESTRIAL_TOOLTIP_SLUG]
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

    habitats.forEach(({ slug, strapiSlug, request }) => {
      const analysis = analyses[requests.findIndex(({ habitat }) => habitat === request)];

      const baselines = [...codes, GLOBAL_CODE].flatMap((code): Baseline[] => {
        const stat = latestStats.get(`${code}|${strapiSlug}`);
        return Number(stat?.total_area)
          ? [{ code, existing: Number(stat.protected_area), total: Number(stat.total_area) }]
          : [];
      });
      // A habitat missing from the response gains nothing in any location
      const contributions = analysis.data
        ? buildContributions(baselines, analysis.data[slug]?.locations_area ?? [], seaCodes)
        : undefined;

      baselines.forEach(({ code }) => {
        const contribution = contributions?.get(code);

        rowsByCode.set(code, [
          ...(rowsByCode.get(code) ?? []),
          {
            slug,
            name: habitatNames?.[strapiSlug] ?? strapiSlug,
            color: HABITAT_COLORS[environment][strapiSlug],
            status: toStatus(analysis),
            contribution,
            tooltip: tooltips[strapiSlug],
          },
        ]);
      });
    });

    return rowsByCode;
  }, [
    stats.data,
    habitats,
    requests,
    analyses,
    codes,
    seaCodes,
    environment,
    habitatNames,
    tooltips,
  ]);

  return {
    habitatsByCode,
    status: toStatus(stats),
    tooltip: tooltips[TERRESTRIAL_TOOLTIP_SLUG],
    loadsAtOnce: requests.length === 1,
  };
};

export default useHabitatContributions;
