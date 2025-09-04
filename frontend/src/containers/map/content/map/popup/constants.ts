import { IconProps } from '@/components/ui/icon';
import Mountain from '@/styles/icons/mountain.svg';
import Wave from '@/styles/icons/wave.svg';

export const POPUP_PROPERTIES_BY_SOURCE = {
  'eez-countries-source': {
    id: 'ISO_TER1',
    name: {
      en: 'name',
      es: 'name_es',
      fr: 'name_fr',
    },
  },
  // TODO TECH-3174: Clean up eez-source after removing old EEZ layer from DB
  'ezz-source': {
    id: 'ISO_SOV1',
    name: {
      en: 'GEONAME',
      es: 'GEONAME_ES',
      fr: 'GEONAME_FR',
    },
  },
  // TODO TECH-3174: Clean up regions-source after removing old marine regions layer from DB
  'regions-source': {
    id: 'region_id',
    name: {
      en: 'name',
      es: 'name_es',
      fr: 'name_fr',
    },
  },
  'marine-regions-source': {
    id: 'region_id',
    name: {
      en: 'name',
      es: 'name_es',
      fr: 'name_fr',
    },
  },
  'gadm-countries': {
    id: 'GID_0',
    name: {
      en: 'COUNTRY',
      es: 'name_es',
      fr: 'name_fr',
    },
  },
  'gadm-regions': {
    id: 'region_id',
    name: {
      en: 'name',
      es: 'name_es',
      fr: 'name_fr',
    },
  },
};

export const POPUP_ICON_BY_SOURCE = {
  // TODO TECH-3174: Clean up eez-source after removing old EEZ layer from DB
  'ezz-source': Wave as IconProps['icon'],
  'regions-source': Wave as IconProps['icon'], // TODO TECH-3174: Clean up
  'eez-countries-source': Wave as IconProps['icon'],
  'marine-regions-source': Wave as IconProps['icon'],
  'gadm-countries': Mountain as IconProps['icon'],
  'gadm-regions': Mountain as IconProps['icon'],
};

export const POPUP_BUTTON_CONTENT_BY_SOURCE = {
  // TODO TECH-3174: Clean up eez-source after removing old EEZ layer from DB
  'ezz-source': 'open-country-insights',
  'regions-source': 'open-region-insights', // TODO TECH-3174: Clean up
  'eez-countries-source': 'open-country-insights',
  'marine-regions-source': 'open-region-insights',
  'gadm-countries': 'open-country-insights',
  'gadm-regions': 'open-region-insights',
};
