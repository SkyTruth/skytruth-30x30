import { useLocale, useTranslations } from 'next-intl';

import { cn } from '@/lib/classnames';
import { formatPercentage } from '@/lib/utils/formats';
import { Contribution } from '@/lib/utils/modelling-contributions';
import { FCWithMessages } from '@/types';

import AddedPercentageBadge from './added-percentage-badge';
import ContributionAxis from './axis';
import ContributionBar from './bar';
import ProtectedAreaText from './protected-area-text';

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

  return (
    <div className={cn('font-mono', className)}>
      <div className="flex items-start justify-between gap-4">
        <div className="shrink-0">
          {/* Protected percentage including the drawn shape (with "+X%") */}
          <div className="-mt-1.5 flex items-center gap-2">
            <span className="pt-[0.2em] text-3xl font-bold leading-none">
              {t.rich('total-percentage', {
                percentage: formatPercentage(locale, totalPercentage, {
                  displayPercentageSign: false,
                }),
                sign: (chunks) => <span className="pl-0.5 text-xs">{chunks}</span>,
              })}
            </span>
            {hasAddedArea && <AddedPercentageBadge percentage={addedPercentage} />}
          </div>
          {/* Percentage before the shape was added ("was X%") */}
          {hasAddedArea && (
            <div className="pt-0.5 text-xs-bold font-bold text-previous-value">
              {t.rich('previous-percentage', {
                percentage: formatPercentage(locale, existingPercentage, {
                  displayPercentageSign: false,
                }),
                sign: (chunks) => <span className="text-[0.7em]">{chunks}</span>,
              })}
            </div>
          )}
        </div>
        {/* Protected area ("+M km²", "N km² of", "T km² protected" on their own lines) */}
        <ProtectedAreaText className="text-right" contribution={contribution} stacked />
      </div>
      {/* Bar chart: existing area then added area */}
      <ContributionBar className="my-2" contribution={contribution} target={target} />
      <ContributionAxis target={target} />
    </div>
  );
};

ContributionChart.messages = ['components.chart-contribution'];

export default ContributionChart;
