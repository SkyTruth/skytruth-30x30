/**
 * pa service
 */

import { factories } from '@strapi/strapi';

import type { ToUpdateRelations, InputPA ,PA, PARelations } from '../controllers/pa';


export default factories.createCoreService('api::pa.pa', ({ strapi }) => ({
  async getRelationMaps(): Promise<{[key: string]: IDMap}>{
    const locationMap = await strapi
      .service('api::location.location')
      .getLocationMap();

    const mpaaProtectionLevelMap = await strapi
      .service('api::mpaa-protection-level.mpaa-protection-level')
      .getMpaaProtectionLevelMap();

    const environmentMap = await strapi
      .service('api::environment.environment')
      .getEnvironmentMap();

    const protectionStatusMap = await strapi
      .service('api::protection-status.protection-status')
      .getProtectionStatusMap();

    const dataSourceMap = await strapi
      .service('api::data-source.data-source')
      .getDataSourceMap();

    const mpaaIucnCategoryMap = await strapi
      .service('api::mpa-iucn-category.mpa-iucn-category')
      .getMpaaIucnCategoryMap();

    const mpaaEstablishmentStageMap = await strapi
      .service('api::mpaa-establishment-stage.mpaa-establishment-stage')
      .getMpaaEstablishmentStageMap();

      return {
        dataSourceMap,
        environmentMap,
        locationMap,
        mpaaEstablishmentStageMap,
        mpaaIucnCategoryMap,
        mpaaProtectionLevelMap,
        protectionStatusMap,
      }

  },
  /**
   * Method to concatenate key fields of a PA that, together, for a unique idnetifier
   * allowing us to relaibly map a PA from WDPA or MPAtlas to a PA within our database
   * @param pa
   * @returns uniquely identifiying pa string
   */
  makePAKey(pa: PA | PARelations): string {
    return `${pa?.environment ?? 'xxx'}-${pa?.wdpaid ?? 'xxx'}-${pa?.wdpa_p_id ?? 'xxx'}-${pa?.zone_id ?? 'xxx'}`
  },
  /**
   * Check to make sure string values of relational data exist in the database
   * and make sure required fields exist on PAs to be created
   * @param pa Protected area
   * @param idMaps ID Maps returned from getRelationMaps above
   * @param errors Error array to be updated
   * @returns boolean, true if all relationships are valid false if not
   */
  validateFields(pa: PA, idMaps: {[key: string]: IDMap}, errors: {msg: string, err: string}[]): boolean {
    const {
      id,
      // relational fields
      data_source,
      environment,
      location,
      iucn_category,
      mpaa_establishment_stage,
      mpaa_protection_level,
      protection_status,
      //required fields
      area,
      bbox,
      coverage,
      name,
    } = pa;
    const {
        dataSourceMap,
        environmentMap,
        locationMap,
        mpaaEstablishmentStageMap,
        mpaaIucnCategoryMap,
        mpaaProtectionLevelMap,
        protectionStatusMap,
      } = idMaps;

    // Validate relational fields
    if (!dataSourceMap[data_source]) {
      errors.push({
          msg: `Failed to find data source for PA, name: ${pa?.name}, id: ${id}`,
          err: `Data source ${data_source} not found`
      });
      return false;
    }
    if (!environmentMap[environment]) {
      errors.push({
          msg: `Failed to find environment for PA, name: ${pa?.name}, id: ${id}`,
          err: `Environment ${environment} not found`
      });
      return false;
    }
    if (!locationMap[location]) {
      errors.push({
          msg: `Failed to find location for PA, name: ${pa?.name}, id: ${id}`,
          err: `Location ${location} not found`
      });
      return false;
    }

    if (mpaa_establishment_stage && !mpaaEstablishmentStageMap[mpaa_establishment_stage]) {
      errors.push({
          msg: `Failed to find MPAA Establishment Stage for PA, name: ${pa?.name}, id: ${id}`,
          err: `Establishment Stage ${mpaa_establishment_stage} not found`
      });
      return false;
    }
    if (iucn_category && !mpaaIucnCategoryMap[iucn_category]) {
      errors.push({
          msg: `Failed to find MPAA IUCN Category for PA, name: ${pa?.name}, id: ${id}`,
          err: `IUCN Category ${iucn_category} not found`
      });
      return false;
    }
      if (mpaa_protection_level && !mpaaProtectionLevelMap[mpaa_protection_level]) {
      errors.push({
          msg: `Failed to find MPAA Protection Level for PA, name: ${pa?.name}, id: ${id}`,
          err: `Protection Level ${mpaa_protection_level} not found`
      });
      return false;
    }
    if (!protectionStatusMap[protection_status]) {
      errors.push({
          msg: `Failed to find Protection Status for PA, name: ${pa?.name}, id: ${id}`,
          err: `Protection Status ${protection_status} not found`
      });
      return false;
    }

    // Validate required fields for net-new PAs
    if (!id) {
      if (!name) {
        errors.push({
          msg: `Failed to create PA, wdpa_id: ${pa?.wdpaid}`,
          err: "Missing required field, 'name'"
        })
        return false
      }
      if (area !== 0 && !area) {
        errors.push({
          msg: `Failed to create PA, name: ${pa?.name}`,
          err: "Missing required field, 'area'"
        })
        return false
      }
      if (!bbox) {
        errors.push({
          msg: `Failed to create PA, name: ${pa?.name}`,
          err: "Missing required field, 'bbox'"
        })
        return false
      }
      if (coverage !== 0 && !coverage) {
        errors.push({
          msg: `Failed to create PA, name: ${pa?.name}`,
          err: "Missing required field, 'coverage'"
        })
        return false
      }
    }

    // All good!
    return true
  },
  /**
   * This function checks a PAs parent and child realtions, if they exist as records in the database
   * then they are passed through and allowd to be created as relationships. If they don't yet exist
   * in the database we record a uniquely identifying key for the relationship and map that key to
   * the current PA so that relationships can be made after the parent or children are added to the DB
   * and have IDs.
   * @param pa Protected Arae
   * @param toUpdateRelations Mapping of parent and child relations that must be updated
   * after first pass of upserting
   * @param newIdMap Map of identifying strings to IDs of newly created PAs
   * @returns
   */
  checkParentChild(pa: InputPA, toUpdateRelations: ToUpdateRelations, newIdMap: IDMap): PA {
    const { children, parent } = pa;
    const paIdentifier = pa?.id ?? this.makePAKey(pa);

      if (children?.length) {
       if (!children.every(child => !!child?.id)) {
        toUpdateRelations[paIdentifier] = { children: []};

        children.forEach(child => {
          toUpdateRelations[paIdentifier].children.push({
            id: child?.id,
            key: this.makePAKey(child)
          })
        })
        /**
         * If we're in this block it means the Pa has childnred
         * and at least one child is missing an ID (i.e. isn't created yet)
         * So we will skip updating children for this PA and make that update
         * after all new PAs are created
         * */
        delete pa.children
      } else {
        //Every child has an ID so just clean up the child objects
        const updatedChildren = children.map(child => child.id);
        pa.children = updatedChildren;
      }
    }


    if (parent) {
      if(!parent?.id) {
        if (!toUpdateRelations[paIdentifier]) {
          toUpdateRelations[paIdentifier] = {parent: {}};
        }
        toUpdateRelations[paIdentifier].parent = {
          key: this.makePAKey(parent)
        }
        /**
         * Parent doesn't yet exist, so save updating that relationship
         * until all new PAs are created
         */
        delete pa.parent
      } else {
        pa.parent = parent.id;
      }
    }
    return pa
  }
}));
