/**
 * protection-coverage-stat controller
 */

import { factories } from '@strapi/strapi'

import {
    ApiEnvironmentEnvironment,
    ApiLocationLocation,
    ApiProtectionCoverageStatProtectionCoverageStat
} from '@/types/generated/contentTypes';

import Logger from '../../../utils/Logger';

const PROTECTION_COVERAGE_STAT_NAMESPACE = 'api::protection-coverage-stat.protection-coverage-stat';
const DEFAULT_PAGE_SIZE = 25;

export default factories.createCoreController(PROTECTION_COVERAGE_STAT_NAMESPACE, ({ strapi }) => ({
    async find(ctx) {
        try {
            const { query } = ctx;
            // find the most recently updated record and return its updatedAt date
            const updatedAtQuery = {
                ...query,
                fields: ['updatedAt'],
                sort: { updatedAt: 'desc' },
                limit: 1
            };
            const updatedAt = await strapi.entityService.findMany(PROTECTION_COVERAGE_STAT_NAMESPACE, updatedAtQuery).then((data) => {
                return data[0]?.updatedAt ?? null;
            });

            const dataQuery = {
                ...query,
                pagination: { pageSize: 1000000, page: 1 } // Max allowed by the API config. Will paginate after sorting
            }
            delete dataQuery.sort; // We will sort the data after we get it
            ctx.query = dataQuery;
            // run the original find function without pagination or sorting
            const { data, meta } = await super.find(ctx);
            // Update sort so null values are at the end
            if (query?.sort) {
                const sortParams = normalizeSortParams(query.sort);
                for (const sortItem in sortParams) {
                    data.sort((a, b) => {
                        const first = getValueByPath(a, sortItem);
                        const second = getValueByPath(b, sortItem);

                        if (first === second) {
                            return 0;
                        }
                        // nulls sort after anything else
                        if (first === null || first === undefined) {
                            return 1;
                        }
                        if (second === null || second === undefined) {
                            return -1;
                        }

                        if (sortParams[sortItem] === 'asc') {
                            return first < second ? -1 : 1;
                        }

                        return first < second ? 1 : -1;
                    })
                }
            }
            const [start, end] = getPaginationBounds(query.pagination, data.length);
            const paginatedData = data.slice(start, end);

            if (!query.pagination) {
                meta.pagination = {
                    page: 1,
                    pageSize: DEFAULT_PAGE_SIZE,
                    pageCount: Math.ceil(data.length / DEFAULT_PAGE_SIZE),
                    totalCount: data.length
                }
            }
            return { data: paginatedData, meta: { ...meta, updatedAt } };
        } catch (error) {
            Logger.error('Error fetching protection coverage stat data: ' + error?.message, error);
            return ctx.badRequest('Error fetching protection coverage stat data');
        }
    }
}));

interface Pagination {
    start?: number;
    limit?: number;
    page?: number;
    pageSize?: number;
}

/**
 * Helper function to get the start and end bounds for pagination
 * @param pagination Object containing pagination parameters. The pair of start and limit are preferred 
 *  over page and pageSize
 * @param dataLength Total length of the data to be paginated
 * @returns start and end (exclusive) bounds for pagination
 */
function getPaginationBounds(pagination: Pagination = {}, dataLength: number): [start: number, end: number] {
    const { start = null, limit = 25, page = 1, pageSize = 25 } = pagination;
    if (limit === -1) {
        return [start ?? 0, dataLength];
    }
    if (start !== null && limit) {
        return [start, start + limit];
    }
    return [(page - 1) * pageSize, page * pageSize];
}

interface ProtectionCoverageStatResponse
    extends ApiProtectionCoverageStatProtectionCoverageStat {
    id: number;
    data?: ApiLocationLocation | ApiEnvironmentEnvironment
}

/**
 * Helper method to get data from a nested object using a string path. Similar to Lodash's get, except it 
 *  also looks for data and attributes keys where appropriate
 * @param data Returned data from the API
 * @param path String path to the desired value, e.g. 'data.attributes.name'
 * @returns 
 */
function getValueByPath(
    data: ProtectionCoverageStatResponse,
    path: string
): keyof ApiProtectionCoverageStatProtectionCoverageStat {
    return path.split('.').reduce((acc, key) => {
        if (!acc) {
            return null;
        }
        if (acc[key]) {
            return acc[key];
        }
        if (acc?.attributes) {
            return acc.attributes[key];
        }
        if (acc?.data) {
            return acc.data?.attributes[key];
        }

    }, data);
}
/**
 * Helper method to flatten deeply nested sort parameters into a sinlge level object
 * with dot notation keys
 * @param sort An object of variable depth containing the sort parameters
 * @example {{ location: { name: 'asc' }, environment: 'asc'  }
 * @param prefix the previous collapsed key
 * @returns a flattened object with dot notation keys
 * @example { 'location.name': 'asc', environment: 'asc' }
 */
function flattenSortParams(
    sort: Record<string, any>,
    prefix: string = ''
): Record<string, string> {
    const flattened: Record<string, string> = {};

    for (const key in sort) {
        if (Object.hasOwn(sort, key)) {
            const value = sort[key];
            const newKey = prefix ? `${prefix}.${key}` : key;
            if (value !== null && typeof value === 'object') {
                Object.assign(flattened, flattenSortParams(value, newKey));
            } else {
                flattened[newKey] = value;
            }
        }
    }

    return flattened;
}

/**
 * * Normalizes sort parameters that might be provided as:
 * a string, e.g. 'year:asc,environment.name:asc'
 * a nested object, e.g. { location: { name: 'asc' } }
 * or an array mixing both formats.
 * @param sortInput 
 * @Returns a flat object with keys in dot-notation.
 * @example { 'location.name': 'asc', environment: 'asc' }
 */
function normalizeSortParams(
    sortInput: string | Record<string, any> | Array<string | Record<string, any>>
): Record<string, string> {
    let sortParams: Record<string, string> = {};

    if (Array.isArray(sortInput)) {
        sortInput.forEach(item => {
            if (typeof item === 'string') {
                // Split by comma to separate sort pairs
                const pairs = item.split(',');
                pairs.forEach(pair => {
                    const [key, order] = pair.split(':');
                    if (key && order) {
                        sortParams[key.trim()] = order.trim();
                    }
                });
            } else if (typeof item === 'object' && item !== null) {
                // Flatten the object and merge its keys
                const flattened = flattenSortParams(item);
                sortParams = { ...sortParams, ...flattened };
            }
        });
    } else if (typeof sortInput === 'string') {
        const pairs = sortInput.split(',');
        pairs.forEach(pair => {
            const [key, order] = pair.split(':');
            if (key && order) {
                sortParams[key.trim()] = order.trim();
            }
        });
    } else if (typeof sortInput === 'object' && sortInput !== null) {
        sortParams = flattenSortParams(sortInput);
    }

    return sortParams;
}