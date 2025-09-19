/**
 * Controller logic for fetching statistics aggregated by location
 */
import { FISHING_PROTECTION_LEVEL_STATS_NAMESPACE } from "../../fishing-protection-level-stat/controllers/fishing-protection-level-stat";
import { HABITAT_STATS_NAMESPACE } from "../../habitat-stat/controllers/habitat-stat";
import { MPAA_PROTECTION_LEVEL_STATS_NAMESPACE } from "../../mpaa-protection-level-stat/controllers/mpaa-protection-level-stat";
import { PROTECTION_COVERAGE_STAT_NAMESPACE } from "../../protection-coverage-stat/controllers/protection-coverage-stat";

const AGGREGATED_STATS_NAMESPACE = 'api::aggregated-stat.aggregated-stat';

export enum Stats {
  ProtectionCoverage = 'protection_coverage',
  Habitat = 'habitat',
  MpaaProtectionLevel = 'mpaa_protection_level',
  FishingProtectionLevel = 'fishing_protection_level',
}
export type AggregatedStats = {
  coverage: number,
  protected_area: number,
  locations: string[],
  total_area: number,
  updatedAt: string,
  environment?: string,
  fishing_protection_level?: string,
  mpaa_protection_level?: string,
  habitat?: string,
  year?: number
}
export type StatsResponse = {
  [key in Stats]?: AggregatedStats[]
}

export default {
  async getStats(ctx): Promise<{data: StatsResponse}> {
    try {
      const { query } = ctx;
      const {
        year,
        locations,
        environment=null,
        stats=Stats.ProtectionCoverage,
        fishing_protection_level=null,
        mpaa_protection_level=null,
        habitat=null
      } = query;

      if (!locations) {
        return ctx.badRequest('locations is not defined');
      }

      const formattedLocs: string[] = locations.split(',');
      const requestedStats: Set<Stats> = new Set(stats.split(','));
      const response = {} as StatsResponse;

      const statsParams = {
        [Stats.ProtectionCoverage]: {
          locations: formattedLocs,
          apiNamespace: PROTECTION_COVERAGE_STAT_NAMESPACE,
          environment, 
          year
        },
        [Stats.Habitat]: {
          locations: formattedLocs,
          apiNamespace: HABITAT_STATS_NAMESPACE,
          environment, 
          year,
          subFieldName: 'habitat',
          subFieldValue: habitat
        },
        [Stats.FishingProtectionLevel]: {
          locations: formattedLocs,
          apiNamespace: FISHING_PROTECTION_LEVEL_STATS_NAMESPACE,
          subFieldName: 'fishing_protection_level',
          subFieldValue: fishing_protection_level
        },
        [Stats.MpaaProtectionLevel]: {
          locations: formattedLocs,
          apiNamespace: MPAA_PROTECTION_LEVEL_STATS_NAMESPACE,
          subFieldName: 'mpaa_protection_level',
          subFieldValue: mpaa_protection_level
        },
      }

      const inputValidation = new Set(Object.values(Stats));
      for (const stat of requestedStats) {
        if (inputValidation.has(stat)) {
          response[stat] = await strapi
          .service(AGGREGATED_STATS_NAMESPACE)
          .getAggregatedStats(statsParams[stat])
        }
      }

      return {data: response};
    } catch (error){
      strapi.log.error("Failed to get aggregated stats", error)
      return ctx.badRequest('something bad happened', {error: error.message})
    }
  }
};
