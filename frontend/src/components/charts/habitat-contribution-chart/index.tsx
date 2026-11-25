import { ComponentProps, PropsWithChildren } from 'react';

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

/**
 * List of habitat rows sharing three columns (name, "+X%" badge, protected percentage),
 * under "Added" and "Total" labels. Each column is as wide as its widest value; every badge
 * fills its column and each percentage is centered in its column, so both line up under
 * their centered labels
 */
export const HabitatContributionList: FCWithMessages<PropsWithChildren<{ className?: string }>> = ({
  className,
  children,
}) => {
  const t = useTranslations('components.chart-contribution');

  return (
    <div className={cn('grid grid-cols-[1fr_auto_auto] gap-x-2', className)}>
      <span
        aria-hidden
        className="col-start-2 justify-self-center font-mono text-xs font-bold text-previous-value"
      >
        {t('added')}
      </span>
      <span
        aria-hidden
        className="justify-self-center font-mono text-xs font-bold text-previous-value"
      >
        {t('total')}
      </span>
      {children}
    </div>
  );
};

HabitatContributionList.messages = ['components.chart-contribution'];

type HabitatContributionChartProps = {
  className?: string;
  title: string;
  color: string;
  contribution: Contribution;
  // Info tooltip next to the habitat name
  tooltip?: ComponentProps<typeof TooltipButton>;
};

/**
 * One habitat row under "Habitat Protection" in the Conservation Builder panel: the habitat
 * name with its "+X%" and protected percentage at the right, a bar of the existing and
 * added area, and the protected km² of the habitat's extent. Goes in a
 * `HabitatContributionList`, whose columns it shares
 */
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
        {formatPercentage(locale, totalPercentage, { displayPercentageSign: false })}
        <span className="text-[0.7em]">%</span>
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
