/* eslint-disable @typescript-eslint/no-var-requires */
import React from 'react';

import { JSONConfiguration, JSONConverter } from '@deck.gl/json';

// import {
//   LegendTypeBasic,
//   LegendTypeChoropleth,
//   LegendTypeGradient,
// } from '@/components/map/legend/item-types';
import BoundariesPopup from '@/containers/map/content/map/popup/boundaries';
import GenericPopup from '@/containers/map/content/map/popup/generic';
import ProtectedAreaPopup from '@/containers/map/content/map/popup/protected-area';
import FUNCTIONS from '@/lib/utils';
import { ParamsConfig, ParamsConfigValue } from '@/types/layers';

export const JSON_CONFIGURATION = new JSONConfiguration({
  React,
  classes: Object.assign(
    //
    {}
    // require('@deck.gl/layers')
    // require('@deck.gl/aggregation-layers')
  ),
  functions: FUNCTIONS,
  enumerations: {},
  reactComponents: {
    GenericPopup,
    ProtectedAreaPopup,
    BoundariesPopup: BoundariesPopup,
    // LegendTypeBasic,
    // LegendTypeChoropleth,
    // LegendTypeGradient,
  },
});

export interface GetParamsProps {
  settings: Record<string, unknown>;
  params_config: ParamsConfig;
}

/**
 * *`getParams`*
 * Get params from params_config
 * @param {Object} params_config
 * @returns {Object} params
 *
 */
export const getParams = ({ params_config, settings = {} }: GetParamsProps) => {
  if (!params_config) {
    return {};
  }

  return params_config.reduce(
    (acc, p) => {
      return {
        ...acc,
        [`${p.key}`]: settings[`${p.key}`] ?? p.default,
      };
    },
    {} as Record<string, unknown>
  );
};

/**
 * Create a new parameter for the params_config array
 * @param name Name of the new parameter
 * @param methodName Name of the (async) function that will compute the value of the parameter
 * @param params Parameters for the (async) function that will compute the value of the parameter
 */
const createNewParamsConfigParam = async (
  name: string,
  methodName: string,
  params: Record<string, unknown>
): Promise<ParamsConfigValue> => {
  return {
    key: name,
    default: await FUNCTIONS[methodName](params),
  };
};

/**
 * Resolve the final params_config after creating any new eventual dynamic parameter
 * @param params_config Initial params_config
 * @param settings Values to replace the defaults of the parameters
 */
export const resolveParamsConfig = async (
  params_config: ParamsConfig,
  settings: Record<string, unknown>
) => {
  let finalParamsConfig = params_config;
  const initParameter = finalParamsConfig.find(({ key }) => key === '_INIT_');

  // If `initParameter` is defined, then we want to asynchronously create new parameters within `pc`
  if (initParameter) {
    const initParameterConfig = initParameter.default as Record<
      string,
      { ['@@function']: string; [attr: string]: unknown }
    >;

    const newParams: ParamsConfigValue[] = [];

    for (const [name, attrs] of Object.entries(initParameterConfig)) {
      const param = await createNewParamsConfigParam(
        name,
        attrs['@@function'],
        Object.entries(attrs).reduce((res, [key, name]) => {
          if (key === '@@function') {
            return res;
          }

          return {
            ...res,
            [key]: getParams({ params_config: finalParamsConfig, settings })[
              (name as string).replace('@@#params.', '')
            ],
          };
        }, {})
      );
      newParams.push(param);
    }

    finalParamsConfig = [...finalParamsConfig, ...newParams];
  }

  return finalParamsConfig;
};

interface ParseConfigurationProps {
  config: unknown;
  params_config: ParamsConfig;
  settings: Record<string, unknown>;
}

/**
 * *`parseConfig`*
 * Parse config with params_config
 * @param {Object} config
 * @param {Object} params_config
 * @returns {Object} config
 *
 */
export const parseConfig = async <T>({
  config,
  params_config,
  settings,
}: ParseConfigurationProps): Promise<T | null> => {
  if (!config || !params_config) {
    return null;
  }

  const JSON_CONVERTER = new JSONConverter({
    configuration: JSON_CONFIGURATION,
  });

  const params = getParams({
    params_config: await resolveParamsConfig(params_config, settings),
    settings,
  });

  // Merge enumerations with config
  JSON_CONVERTER.mergeConfiguration({
    enumerations: {
      params,
    },
  });

  return JSON_CONVERTER.convert(config) as T;
};
