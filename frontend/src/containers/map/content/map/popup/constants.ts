import { IconProps } from '@/components/ui/icon';
import Mountain from '@/styles/icons/mountain.svg';
import Wave from '@/styles/icons/wave.svg';

export const EEZ_SOURCE = 'eez-countries-source';

export const POPUP_PROPERTIES_BY_SOURCE = {
  // TODO TECH-3174: Clean up eez-source after removing old EEZ layer from DB
  'ezz-source': {
    ids: ['ISO_SOV1'],
    name: {
      en: 'GEONAME',
      es: 'GEONAME_ES',
      fr: 'GEONAME_FR',
    },
  },
  // TODO TECH-3174: Clean up regions-source after removing old marine regions layer from DB
  'regions-source': {
    ids: ['region_id'],
    name: {
      en: 'name',
      es: 'name_es',
      fr: 'name_fr',
    },
  },
  // TODO TECH-3174: Clean up regions-source after removing old marine regions layer from DB
  'gadm-countries': {
    ids: ['GID_0'],
    name: {
      en: 'COUNTRY',
      es: 'name_es',
      fr: 'name_fr',
    },
  },
  // TODO TECH-3174: Clean up regions-source after removing old marine regions layer from DB
  'gadm-regions': {
    ids: ['region_id'],
    name: {
      en: 'name',
      es: 'name_es',
      fr: 'name_fr',
    },
  },
  [EEZ_SOURCE]: {
    ids: ['ISO_TER1', 'ISO_TER2', 'ISO_TER3', 'ISO_SOV1', 'ISO_SOV2', 'ISO_SOV3'],
    name: {
      en: 'name',
      es: 'name_es',
      fr: 'name_fr',
      pt: 'name_pt'
    },
  },
  'marine-regions-source': {
    ids: ['region_id'],
    name: {
      en: 'name',
      es: 'name_es',
      fr: 'name_fr',
      pt: 'name_pt'
    },
  },
  countries: {
    // There's currently on sov1 and sov2 but the code allows for sov3
    ids: ['location', 'ISO_SOV1', 'ISO_SOV2', 'ISO_SOV3'],
    name: {
      en: 'name',
      es: 'name_es',
      fr: 'name_fr',
      pt: 'name_pt'
    },
  },
  'terrestrial-regions': {
    ids: ['region_id'],
    name: {
      en: 'name',
      es: 'name_es',
      fr: 'name_fr',
      pt: 'name_pt'
    },
  },
};

export const POPUP_ICON_BY_SOURCE = {
  // TODO TECH-3174: Clean up eez-source after removing old EEZ layer from DB
  'ezz-source': Wave as IconProps['icon'], // TODO TECH-3174: Clean up
  'regions-source': Wave as IconProps['icon'], // TODO TECH-3174: Clean up
  'gadm-countries': Mountain as IconProps['icon'], // TODO TECH-3174: Clean up
  'gadm-regions': Mountain as IconProps['icon'], // TODO TECH-3174: Clean up
  [EEZ_SOURCE]: Wave as IconProps['icon'],
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
  [EEZ_SOURCE]: 'open-country-insights',
  'marine-regions-source': 'open-region-insights',
  countries: 'open-country-insights',
  'gadm-regions': 'open-region-insights',
};

export const CUSTOM_REGION_ELIGABILITY_BY_SOURCE = new Set(['countries', EEZ_SOURCE]);
