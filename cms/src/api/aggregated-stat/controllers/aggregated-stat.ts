/**
 * A set of functions called "actions" for `aggregated-stats`
 */
import { PROTECTION_COVERAGE_STAT_NAMESPACE } from "../../protection-coverage-stat/controllers/protection-coverage-stat";

export default {
  async getStats(ctx) {
    try {
      const { query } = ctx;
      const { year, locations, environement, stats } = query;

      if (!locations) {
        return ctx.badRequest('locations is not defined');
      }
      const formattedLocs = locations.split(',');

      const stat = await strapi
        .service(PROTECTION_COVERAGE_STAT_NAMESPACE)
        .getAggregatedStats(formattedLocs, environement, year);

      
      return stat;
    } catch (error){
      return ctx.badRequest('something bad happened', {error})
    }
  }

};
