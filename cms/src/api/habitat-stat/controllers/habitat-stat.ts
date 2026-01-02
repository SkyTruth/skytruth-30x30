/**
 * habitat-stat controller
 */

import { factories } from '@strapi/strapi'

export const HABITAT_STATS_NAMESPACE = 'api::habitat-stat.habitat-stat';

export default factories.createCoreController(HABITAT_STATS_NAMESPACE, ({ strapi }) => ({
    async bulkUpsert(ctx) {
        try {
            const { data } = ctx?.request?.body;
            if (!Array.isArray(data)) {
                return ctx.badRequest('Data must be an array');
            }
            const year = parseInt(ctx.params.year, 10);
            if (isNaN(year)) {
                return ctx.badRequest('Year must be a valid number');
            }
            const errors = [];
            let locationMap: IDMap | null = null;
            let habitatMap: IDMap | null = null;
            let environmentMap: IDMap | null = null;

            const habitatStatMap: IDMap = await strapi
                .service(HABITAT_STATS_NAMESPACE)
                .getHabitatStatMap(year);

            await strapi.db.transaction(async () => {
                for (const stat of data) {
                    const { protected_area, total_area } = stat;
                    const statKey = `${stat.location}-${stat.environment}-${stat.habitat}`;

                    // No existing record, create a new one
                    if (!habitatStatMap[statKey]) {
                        if (!locationMap) {
                            locationMap = await strapi
                                .service('api::location.location')
                                .getLocationMap();
                        }
                        if (!locationMap[stat.location]) {
                            errors.push({
                                msg: `Failed to find location for stat: ${statKey}`,
                                err: `Location ${stat.location} not found`
                            });
                            continue;
                        }
                        if (!habitatMap) {
                            habitatMap = await strapi
                                .service('api::habitat.habitat')
                                .getHabitatMap();
                        }
                        if (!habitatMap[stat.habitat]) {
                            errors.push({
                                msg: `Failed to find habitat for stat: ${statKey}`,
                                err: `Habitat ${stat.habitat} not found`
                            });
                            continue;
                        }
                        if (!environmentMap) {
                            environmentMap = await strapi
                                .service('api::environment.environment')
                                .getEnvironmentMap();
                        }
                        if (!environmentMap[stat.environment]) {
                            errors.push({
                                msg: `Failed to find environment for stat: ${statKey}`,
                                err: `Environment ${stat.environment} not found`
                            });
                            continue;
                        }
                        await strapi.entityService.create(
                            HABITAT_STATS_NAMESPACE,
                            {
                                data: {
                                    year,
                                    total_area,
                                    protected_area,
                                    location: locationMap[stat.location],
                                    habitat: habitatMap[stat.habitat],
                                    environment: environmentMap[stat.environment]
                                }
                            }
                        );
                    } else {
                        // Existing record, update it
                        await strapi.entityService.update(
                            HABITAT_STATS_NAMESPACE,
                            habitatStatMap[statKey],
                            {
                                data: { total_area, protected_area }
                            }
                        );
                    }
                }
            });
            return ctx.send({
                message: 'Bulk upsert completed successfully',
                errors: errors.length > 0 ? errors : null,
            });
        } catch (error) {
            strapi.log.error('Error in habitat-stat bulkUpsert:', error);
            return ctx.internalServerError('An internal server error occurred during bulk upsert');
        }
    }
}));
