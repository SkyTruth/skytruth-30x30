import { ComponentProps } from 'react';

import { useLocale } from 'next-intl';

import TooltipButton from '@/components/tooltip-button';
import { useGetDataInfos } from '@/types/generated/data-info';

export type DataInfoTooltip = Pick<ComponentProps<typeof TooltipButton>, 'text' | 'sources'>;

const NO_TOOLTIPS: Record<string, DataInfoTooltip> = {};

/** Info tooltips (text and linked sources) from Strapi data-info entries, keyed by slug */
const useDataInfoTooltips = (slugs: string[], { enabled = true } = {}) => {
  const locale = useLocale();

  const { data } = useGetDataInfos<Record<string, DataInfoTooltip>>(
    { locale, filters: { slug: { $in: slugs } }, populate: 'data_sources' },
    {
      query: {
        enabled,
        select: ({ data }) =>
          Object.fromEntries(
            data.map(({ slug, content, data_sources }) => [
              slug,
              {
                text: content,
                sources: data_sources?.map(({ documentId, slug, title, url }) => ({
                  documentId,
                  slug,
                  title,
                  url,
                })),
              },
            ])
          ),
      },
    }
  );

  return data ?? NO_TOOLTIPS;
};

export default useDataInfoTooltips;
