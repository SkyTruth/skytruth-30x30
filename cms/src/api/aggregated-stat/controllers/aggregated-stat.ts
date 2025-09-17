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

export default {
  async getStats(ctx) {
    try {
      const { query } = ctx;
      const { year, locations, environment, stats=Stats.ProtectionCoverage } = query;

      if (!locations) {
        return ctx.badRequest('locations is not defined');
      }
      const formattedLocs = locations.split(',');
      const requestedStats: Set<Stats> = new Set(stats.split(','));
      console.log(requestedStats)
      const response = {};

      for (const stat of requestedStats) {
        console.log("Stat!", stat)
        switch (stat) {
          case Stats.ProtectionCoverage:
            response[stat] = await strapi
              .service(PROTECTION_COVERAGE_STAT_NAMESPACE)
              .getAggregatedStats(formattedLocs, environment, year);
          case Stats.Habitat:
            response[stat] = await strapi
              .service("api::habitat-stat.habitat-stat")
              .getAggregatedStats(formattedLocs, environment, year);
        
          default:
            break;
        }
      }
      return {data: response};
    } catch (error){
      return ctx.badRequest('something bad happened', {error})
    }
  }

};
