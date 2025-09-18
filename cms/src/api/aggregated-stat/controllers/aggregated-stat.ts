/**
 * A set of functions called "actions" for `aggregated-stats`
 */
import { PROTECTION_COVERAGE_STAT_NAMESPACE } from "../../protection-coverage-stat/controllers/protection-coverage-stat";

enum Stats {
  ProtectionCoverage = 'protectionCoverage',
  Habitat = 'habitat',
  MpaaProtectionLevel = 'MpaaProtectionLevel',
  FishingProtectionLevel = 'FishingProtectionLevel',
}

type StatsResponse = {
  [key in Stats]?: {
    coverage: number,
    habitat?: string,
    protected_area: number,
    records?: number,
    total_area: number,
    year?: number
  }[]
}

export default {
  async getStats(ctx): Promise<{data: StatsResponse}> {
    try {
      const { query } = ctx;
      const { year, locations, environment, stats=Stats.ProtectionCoverage, fishing_protection_level, mpaa_protection_level } = query;

      if (!locations) {
        return ctx.badRequest('locations is not defined');
      }

      const formattedLocs: string[] = locations.split(',');
      const requestedStats: Set<Stats> = new Set(stats.split(','));
      const response = {} as StatsResponse;

      const statsGetters = {
        [Stats.ProtectionCoverage]: async () => strapi
          .service(PROTECTION_COVERAGE_STAT_NAMESPACE)
          .getAggregatedStats(formattedLocs, environment, year),
        [Stats.Habitat]: async () => strapi
          .service("api::habitat-stat.habitat-stat")
          .getAggregatedStats(formattedLocs, environment, year),
        [Stats.FishingProtectionLevel]: async () => strapi
          .service("api::fishing-protection-level-stat.fishing-protection-level-stat")
          .getAggregatedStats(formattedLocs, fishing_protection_level),
        [Stats.MpaaProtectionLevel]: async () => strapi
          .service('api::mpaa-protection-level-stat.mpaa-protection-level-stat')
          .getAggregatedStats(formattedLocs, mpaa_protection_level)
      }

      const inputValidation = new Set(Object.values(Stats));
      for (const stat of requestedStats) {
        if (inputValidation.has(stat)) {
          response[stat] = await statsGetters[stat]()

        }
      }

      return {data: response};
    } catch (error){
      strapi.log.error("Failed to get aggregated stats", error)
      return ctx.badRequest('something bad happened', {error: error.message})
    }
  }

};
