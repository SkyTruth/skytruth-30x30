import { ALL_TERRITORIES } from "./constants";

export default function filterSovereigns(locationFilter) {
      const code = locationFilter?.code;
      if (code && typeof code === 'string' && ALL_TERRITORIES.has(code)) {
          locationFilter = { code: `${code}*` }
      } else if (code && typeof code === 'object' && code['$eq'] && ALL_TERRITORIES.has(code['$eq'])) {
          locationFilter = {
              code:{
                  '$eq': `${code['$eq']}*`
              }
          }
      }
  return locationFilter
}