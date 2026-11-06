import { useLocale, useTranslations } from 'next-intl';

import { cn } from '@/lib/classnames';
import { formatKM, formatPercentage } from '@/lib/utils/formats';
import { Contribution } from '@/lib/utils/modelling-contributions';
import { FCWithMessages } from '@/types';

const MAX_PERCENTAGE = 100;

type ContributionChartProps = {
  className?: string;
  contribution: Contribution;
  target?: number;
};

/**
 * One stat block in the Conservation Builder panel, e.g. "Marine Conservation Coverage":
 * the protected percentage, how much the drawn shape adds in percent and km², and a
 * bar chart showing the existing and added area
 */
const ContributionChart: FCWithMessages<ContributionChartProps> = ({
  className,
  contribution,
  target,
}) => {
  const t = useTranslations('components.chart-contribution');
  const locale = useLocale();

  const { existing, added, total, existingPercentage, addedPercentage, totalPercentage } =
    contribution;
  // The "+X%" badge and "was X%" display when the drawn shape adds area
  const hasAddedArea = added > 0;
  const hasTarget = target != null;

  const toWidth = (percentage: number) => `${Math.min(percentage, MAX_PERCENTAGE)}%`;

  return (
    <div className={cn('font-mono', className)}>
      <div className="flex items-start justify-between gap-4">
        <div className="shrink-0">
          {/* Protected percentage including the drawn shape (with "+X%") */}
          <div className="flex items-start gap-2">
            <span className="text-3xl font-bold leading-none">
              {formatPercentage(locale, totalPercentage, { displayPercentageSign: false })}
              <span className="pl-0.5 text-xs">%</span>
            </span>
            {hasAddedArea && (
              <span className="inline-flex items-center bg-blue-700 px-1.5 pb-[0.27em] pt-[0.47em] text-base font-bold leading-none text-white">
                <span>
                  {t('added-percentage', {
                    percentage: formatPercentage(locale, addedPercentage, {
                      displayPercentageSign: false,
                    }),
                  })}
                  <span className="text-[0.7em]">%</span>
                </span>
              </span>
            )}
          </div>
          {/* Percentage before the shape was added ("was X%") */}
          {hasAddedArea && (
            <div className="pt-0.5 text-xs font-bold text-previous-value">
              {t('previous-percentage', {
                percentage: formatPercentage(locale, existingPercentage),
              })}
            </div>
          )}
        </div>
        {/* Protected area ("N km² (+M km²) of T km² protected") */}
        <div className="text-right text-xs">
          {t.rich('protected-area', {
            protectedArea: formatKM(locale, existing + added),
            addedArea: formatKM(locale, added),
            totalArea: formatKM(locale, total),
            added: (chunks) => <span className="text-blue-700">{chunks}</span>,
          })}
        </div>
      </div>
      {/* Bar chart: existing area then added area */}
      <div className="relative my-2 h-3.5">
        <span className="absolute top-1/2 h-px w-full border-b border-dashed border-black" />
        <span
          className="absolute bottom-0 left-0 top-0 bg-existing-area"
          style={{ width: toWidth(existingPercentage) }}
        />
        <span
          className="absolute bottom-0 top-0 bg-blue-700"
          style={{ left: toWidth(existingPercentage), width: toWidth(addedPercentage) }}
        />
        {hasTarget && (
          <span
            className="absolute -bottom-1 -top-1 w-0.5 -translate-x-1/2 bg-orange-700"
            style={{ left: toWidth(target) }}
          />
        )}
      </div>
      {/* Axis labels: 0%, the target label under its marker, 100% */}
      <div className="relative flex justify-between text-xs">
        <span>{t('percentage', { percentage: 0 })}</span>
        {hasTarget && (
          <span
            className="absolute -translate-x-1/2 whitespace-nowrap font-bold text-orange-700"
            style={{ left: toWidth(target) }}
          >
            {t('target', { percentage: target })}
          </span>
        )}
        <span>{t('percentage', { percentage: MAX_PERCENTAGE })}</span>
      </div>
    </div>
  );
};

ContributionChart.messages = ['components.chart-contribution'];

export default ContributionChart;
