import { useLocale, useTranslations } from 'next-intl';

import { cn } from '@/lib/classnames';
import { formatPercentage } from '@/lib/utils/formats';
import { Contribution } from '@/lib/utils/modelling-contributions';
import { FCWithMessages } from '@/types';

import {
  AddedPercentageBadge,
  ContributionBar,
  MAX_PERCENTAGE,
  ProtectedAreaText,
  toWidth,
} from './parts';

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

  const { added, existingPercentage, addedPercentage, totalPercentage } = contribution;
  // The "+X%" badge and "was X%" display when the drawn shape adds area
  const hasAddedArea = added > 0;
  const hasTarget = target != null;

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
            {hasAddedArea && <AddedPercentageBadge percentage={addedPercentage} />}
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
        <ProtectedAreaText className="text-right" contribution={contribution} />
      </div>
      {/* Bar chart: existing area then added area */}
      <ContributionBar className="my-2" contribution={contribution} target={target} />
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
