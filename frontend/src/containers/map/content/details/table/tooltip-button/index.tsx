import TooltipButton from '@/components/tooltip-button';
import type { Source } from '@/components/tooltip-button';

type TableTooltipButtonProps = {
  tooltip: { text: string; sources?: Source | Source[] };
};

const TableTooltipButton: React.FC<TableTooltipButtonProps> = ({ tooltip }) => {
  const tooltipText = tooltip?.text;
  const tooltipSources = tooltip?.sources;
  if (!tooltipText) return null;
  return <TooltipButton text={tooltipText} sources={tooltipSources} />;
};

export default TableTooltipButton;
