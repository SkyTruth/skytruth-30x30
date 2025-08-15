/**
 * mpaa-protection-level-stat controller
 */

import { factories } from '@strapi/strapi'

import filterSovereigns from '../../../utils/filter-sovereigns';

export default factories
  .createCoreController('api::mpaa-protection-level-stat.mpaa-protection-level-stat', ({ strapi }) => ({
    // TODO TECH-3174: Clean up custom find method
    async find(ctx) {
      try {
        const { query } = ctx;

        let locationFilter = query?.filters?.location;
        if (locationFilter) {
            query.filters.location = filterSovereigns({...locationFilter})
        }
        return await super.find(ctx)
      } catch (error) {
            strapi.log.error('Error fetching ma protection coverage stat data: ' + error?.message, error);
            return ctx.badRequest('Error fetching protection coverage stat data');
      }
    },
    async bulkUpsert(ctx) {
      try {
        const { data } = ctx.request?.body;
        if (!Array.isArray(data)) {
            return ctx.badRequest('Data must be an array');
        }
        const errors = [];
        let locationMap: IDMap | null = null;
        let MpaaProtectionLevelMap: IDMap | null = null;

        await strapi.db.transaction(async () => {
          const statsMap = await strapi
          .service('api::mpaa-protection-level-stat.mpaa-protection-level-stat')
          .getStatsMap();

          for  (const stat of data) {
            const { area, percentage, total_area } = stat;
            const statKey = `${stat.location}-${stat.mpaa_protection_level}`;

            // No existing record, create a new one
            if (!statsMap[statKey]) {
              if (!locationMap) {
                locationMap = await strapi
                  .service('api::location.location')
                  .getLocationMap();
              }
              if (!locationMap[stat.location]) {
                errors.push({
                  msg: `Location ${stat.location} not found`
                });
                continue;
              }
              if (!MpaaProtectionLevelMap) {
                MpaaProtectionLevelMap = await strapi
                  .service('api::mpaa-protection-level.mpaa-protection-level')
                  .getMpaaProtectionLevelMap();
              }
              if (!MpaaProtectionLevelMap[stat.mpaa_protection_level]) {
                errors.push({
                  msg: `MPAA Protection Level ${stat.mpaa_protection_level} not found`
                });
                continue;
              }
              await strapi.entityService.create(
                'api::mpaa-protection-level-stat.mpaa-protection-level-stat',
                {
                  data: {
                    area,
                    percentage,
                    total_area,
                    location: locationMap[stat.location],
                    mpaa_protection_level: MpaaProtectionLevelMap[stat.mpaa_protection_level],
                  },
                }
              );
            } else {
              // Update the existing record
              await strapi.entityService.update(
                'api::mpaa-protection-level-stat.mpaa-protection-level-stat',
                statsMap[statKey],
                {
                  data: {
                    area,
                    percentage,
                    total_area,
                  },
                }
              );
            }
          }
        })
      return ctx.send({
        message: 'MPAA Protection Level Stats updated successfully.',
        errors: errors.length > 0 ? errors : null,
        updatedCount: data.length - errors.length,
        });
      } catch (error) {
        strapi.log.error('Error in mpaa protection level stats bulkUpdate:', error);
        return ctx.internalServerError('An error occurred while processing the request.', error.message);
      }
    }
  }));
