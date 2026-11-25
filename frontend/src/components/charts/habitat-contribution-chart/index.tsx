import { ComponentProps } from 'react';

import { useLocale, useTranslations } from 'next-intl';

import AddedPercentageBadge from '@/components/charts/contribution-chart/added-percentage-badge';
import ContributionBar from '@/components/charts/contribution-chart/bar';
import { MAX_PERCENTAGE } from '@/components/charts/contribution-chart/helpers';
import ProtectedAreaText from '@/components/charts/contribution-chart/protected-area-text';
import TooltipButton from '@/components/tooltip-button';
import { cn } from '@/lib/classnames';
import { formatPercentage } from '@/lib/utils/formats';
import { Contribution } from '@/lib/utils/modelling-contributions';
import { FCWithMessages } from '@/types';

type HabitatContributionChartProps = {
  className?: string;
  title: string;
  color: string;
  contribution: Contribution;
  // Info tooltip next to the habitat name
  tooltip?: ComponentProps<typeof TooltipButton>;
};

/** One habitat row; must be a child of `HabitatContributionList` */
const HabitatContributionChart: FCWithMessages<HabitatContributionChartProps> = ({
  className,
  title,
  color,
  contribution,
  tooltip,
}) => {
  const t = useTranslations('components.chart-contribution');
  const locale = useLocale();

  const { added, addedPercentage, totalPercentage } = contribution;

  return (
    <div className={cn('col-span-full grid grid-cols-subgrid items-center', className)}>
      <div className="flex items-center gap-1">
        <span className="text-base font-bold">{title}</span>
        {tooltip && <TooltipButton side="right" {...tooltip} />}
      </div>
      {added > 0 ? (
        <AddedPercentageBadge
          className="justify-center justify-self-stretch pb-[0.1em] pt-[0.3em] font-mono text-sm"
          percentage={addedPercentage}
        />
      ) : (
        <span />
      )}
      <span className="justify-self-center pt-[0.2em] font-mono text-base font-bold leading-none">
        {t.rich('total-percentage', {
          percentage: formatPercentage(locale, totalPercentage, { displayPercentageSign: false }),
          sign: (chunks) => <span className="text-[0.7em]">{chunks}</span>,
        })}
      </span>
      <div className="col-span-full flex items-center gap-1 pt-2 font-mono">
        <ContributionBar className="flex-1" contribution={contribution} existingColor={color} />
        <span className="text-xs">{t('percentage', { percentage: MAX_PERCENTAGE })}</span>
      </div>
      <ProtectedAreaText className="col-span-full pt-2 font-mono" contribution={contribution} />
    </div>
  );
};

HabitatContributionChart.messages = ['components.chart-contribution', ...TooltipButton.messages];

export default HabitatContributionChart;
