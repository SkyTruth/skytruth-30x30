import { useLocale, useTranslations } from 'next-intl';

import TooltipButton from '@/components/tooltip-button';
import { cn } from '@/lib/classnames';
import { FCWithMessages } from '@/types';
import { useGetDataInfos } from '@/types/generated/data-info';

interface ChartLegendProps {
  className?: string;
  displayTarget?: boolean;
  displayTargetLine?: boolean;
  target?: number;
  targetYear?: number;
  ortRecord?: string;
  tooltipSlug: string;
  displayProjections?: boolean;
}

const ChartLegend: FCWithMessages<ChartLegendProps> = ({
  className,
  displayTarget,
  displayTargetLine = true,
  target,
  targetYear,
  ortRecord,
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
      populate: 'data_sources',
    },
    {
      query: {
        select: ({ data }) => data?.[0],
        placeholderData: { data: [] },
      },
    }
  );

  const sources = dataInfo?.data_sources?.map(({ documentId, slug, title, url }) => ({
    documentId,
    slug,
    title,
    url: url?.replace('{ort_record}', ortRecord ?? ''),
  }));

  return (
    <div
      className={cn('ml-8 mt-2 flex flex-wrap justify-between gap-3 text-xs text-black', className)}
    >
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
          {displayTargetLine && (
            <span className="block w-10 border-b border-dashed border-orange"></span>
          )}
          <span>
            <span className="relative top-px">
              {t.rich('target-xx-by', {
                target,
                year: targetYear,
              })}
            </span>
            <TooltipButton
              text={dataInfo?.content
                .replace('{target}', `${target}`)
                .replace('{target_year}', `${targetYear}`)}
              sources={sources}
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
