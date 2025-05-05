import { ReactElement, isValidElement, useMemo } from 'react';

import { useLocale } from 'next-intl';

import BoundariesPopup from '@/containers/map/content/map/popup/boundaries';
import GenericPopup from '@/containers/map/content/map/popup/generic';
import ProtectedAreaPopup from '@/containers/map/content/map/popup/protected-area';
import useResolvedConfig from '@/hooks/use-resolved-config';
import { FCWithMessages } from '@/types';
import { useGetLayers } from '@/types/generated/layer';
import { InteractionConfig, LayerTyped } from '@/types/layers';

export interface PopupItemProps {
  slug: string;
}
const PopupItem: FCWithMessages<PopupItemProps> = ({ slug }) => {
  const locale = useLocale();

  const { data: layer, isFetching } = useGetLayers(
    {
      //   // eslint-disable-next-line @typescript-eslint/ban-ts-comment
      //   // @ts-ignore
      filters: {
        slug: {
          $eq: slug,
        },
      },
      locale,
      sort: 'interaction_config',
      populate: 'metadata',
    },
    {
      query: {
        select: ({ data }) => data[0]?.attributes,
      },
    }
  );

  let interaction_config = {};
  let params_config = null;
  if (!isFetching) {
    interaction_config = (layer as LayerTyped)?.interaction_config;
    params_config = (layer as LayerTyped)?.params_config;
  }

  const configParams = useMemo(
    () => ({
      config: {
        ...interaction_config,
        layerSlug: slug,
      },
      params_config,
      settings: {},
    }),
    [slug, interaction_config, params_config]
  );

  const parsedConfig = useResolvedConfig<InteractionConfig | ReactElement>(configParams);

  const INTERACTION_COMPONENT = useMemo(() => {
    if (!parsedConfig) return null;

    if (isValidElement(parsedConfig)) {
      return parsedConfig;
    }

    return null;
  }, [parsedConfig]);

  return INTERACTION_COMPONENT;
};

PopupItem.messages = [
  // These components are used by `parseConfig`
  ...GenericPopup.messages,
  ...ProtectedAreaPopup.messages,
  ...BoundariesPopup.messages,
];

export default PopupItem;
