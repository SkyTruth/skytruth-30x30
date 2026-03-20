import { useLocale } from 'next-intl';

import { useGetDataInfos } from '@/types/generated/data-info';

const TOOLTIP_MAPPING = {
  administrativeBoundary: 'administrative-boundary',
  contributionDetails: 'contribution-details',
  globalContribution: 'global-contribution-model',
};

const useTooltips = () => {
  const locale = useLocale();

  const { data: dataInfo } = useGetDataInfos(
    { locale },
    {
      query: {
        select: ({ data }) => data,
        placeholderData: { data: [] },
      },
    }
  );

  const tooltips = {};

  Object.entries(TOOLTIP_MAPPING).map(([key, value]) => {
    const tooltip = dataInfo.find( item  => item.slug === value)
      ?.content;

    if (!tooltip) return;
    tooltips[key] = tooltip;
  });

  return tooltips;
};

export default useTooltips;
