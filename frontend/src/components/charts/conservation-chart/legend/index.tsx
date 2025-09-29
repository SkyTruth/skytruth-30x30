import { useLocale, useTranslations } from 'next-intl';

import TooltipButton from '@/components/tooltip-button';
import { FCWithMessages } from '@/types';
import { useGetDataInfos } from '@/types/generated/data-info';

interface ChartLegendProps {
  displayTarget?: boolean;
  target?: number;
  targetYear?: number;
  tooltipSlug: string;
  displayProjections?: boolean;
}

const ChartLegend: FCWithMessages<ChartLegendProps> = ({
  displayTarget,
  target,
  targetYear,
  tooltipSlug,
  displayProjections,
}) => {
  const t = useTranslations('components.chart-conservation');
  const locale = useLocale();

  const { data: dataInfo } = useGetDataInfos(
    {
      locale,
      filters: {
        slug: tooltipSlug,
      },
    },
    {
      query: {
        select: ({ data }) => data?.[0],
        placeholderData: { data: [] },
      },
    }
  );

  return (
    <div className="ml-8 mt-2 flex flex-wrap justify-between gap-3">
      {displayProjections && (
        <>
          <span className="inline-flex items-center gap-3">
            <span className="block w-10 border-b border-violet"></span>
            <span>{t('historical-trend')}</span>
          </span>
          <span className="inline-flex items-center gap-3">
            <span className="block w-10 border-b border-dashed border-violet"></span>
            <span>{t('future-projection')}</span>
          </span>
        </>
      )}
      {displayTarget && (
        <span className="inline-flex w-full items-center gap-3">
          <span className="block w-10 border-b border-dashed border-orange"></span>
          <span>
            {t.rich('target-xx-by', {
              target,
              year: targetYear,
            })}
            <TooltipButton
              text={dataInfo?.attributes.content
                .replace('{target}', `${target}`)
                .replace('{target_year}', `${targetYear}`)}
              className="align-bottom hover:bg-transparent"
            />
          </span>
        </span>
      )}
    </div>
  );
};

ChartLegend.messages = ['components.chart-conservation'];

export default ChartLegend;
