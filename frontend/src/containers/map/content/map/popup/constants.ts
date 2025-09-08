import { IconProps } from '@/components/ui/icon';
import Mountain from '@/styles/icons/mountain.svg';
import Wave from '@/styles/icons/wave.svg';

export const POPUP_PROPERTIES_BY_SOURCE = {
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
  // TODO TECH-3174: Clean up regions-source after removing old marine regions layer from DB
  'gadm-countries': {
    id: 'GID_0',
    name: {
      en: 'COUNTRY',
      es: 'name_es',
      fr: 'name_fr',
    },
  },
  // TODO TECH-3174: Clean up regions-source after removing old marine regions layer from DB
  'gadm-regions': {
    id: 'region_id',
    name: {
      en: 'name',
      es: 'name_es',
      fr: 'name_fr',
    },
  },
  'eez-countries-source': {
    id: 'ISO_TER1',
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
  countries: {
    id: 'location',
    name: {
      en: 'name',
      es: 'name_es',
      fr: 'name_fr',
    },
  },
  'terrestrial-regions': {
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
  'ezz-source': Wave as IconProps['icon'], // TODO TECH-3174: Clean up
  'regions-source': Wave as IconProps['icon'], // TODO TECH-3174: Clean up
  'gadm-countries': Mountain as IconProps['icon'], // TODO TECH-3174: Clean up
  'gadm-regions': Mountain as IconProps['icon'], // TODO TECH-3174: Clean up
  'eez-countries-source': Wave as IconProps['icon'],
  'marine-regions-source': Wave as IconProps['icon'],
  countries: Mountain as IconProps['icon'],
  'terrestrial-regions': Mountain as IconProps['icon'],
};

export const POPUP_BUTTON_CONTENT_BY_SOURCE = {
  // TODO TECH-3174: Clean up eez-source after removing old EEZ layer from DB
  'ezz-source': 'open-country-insights', // TODO TECH-3174: Clean up
  'regions-source': 'open-region-insights', // TODO TECH-3174: Clean up
  'gadm-countries': 'open-country-insights', // TODO TECH-3174: Clean up
  'terrestrial-regions': 'open-region-insights', // TODO TECH-3174: Clean up
  'eez-countries-source': 'open-country-insights',
  'marine-regions-source': 'open-region-insights',
  countries: 'open-country-insights',
  'gadm-regions': 'open-region-insights',
};
