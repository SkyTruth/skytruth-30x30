import { Fragment, ReactNode, useState } from 'react';

import Linkify from 'react-linkify';

import { Info } from 'lucide-react';
import { useTranslations } from 'next-intl';

import { Button } from '@/components/ui/button';
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover';
import { cn } from '@/lib/classnames';
import { FCWithMessages } from '@/types';

interface Source {
  id: number;
  title: string;
  url: string;
}

interface TooltipButtonProps {
  className?: string;
  text: string;
  sources?: Source | Source[];
  extraContent?: ReactNode;
}

const TooltipButton: FCWithMessages<TooltipButtonProps> = ({
  className,
  text,
  sources,
  extraContent,
}) => {
  const t = useTranslations('components.tooltip-button');

  const [isTooltipOpen, setIsTooltipOpen] = useState<boolean>(false);

  return (
    <Popover open={isTooltipOpen} onOpenChange={setIsTooltipOpen}>
      <PopoverTrigger asChild>
        <Button
          className={cn('h-auto w-auto pl-1.5 hover:bg-transparent', className)}
          size="icon"
          variant="ghost"
        >
          <span className="sr-only">{t('info')}</span>
          <Info className="h-4 w-4" aria-hidden="true" />
        </Button>
      </PopoverTrigger>
      <PopoverContent
        align="center"
        className="flex max-w-[300px] flex-col gap-6 font-mono text-xs"
      >
        {text && (
          <span>
            <Linkify
              componentDecorator={(href, text, key) => (
                <a
                  className="break-all underline"
                  href={href}
                  key={key}
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  {text}
                </a>
              )}
            >
              {text}
            </Linkify>
          </span>
        )}

        {Array.isArray(sources) && (
          <div className="">
            <span>{t('data-sources:')} </span>
            {sources.map(({ id, title, url }, index) => (
              <Fragment key={id}>
                <a
                  href={url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="font-semibold underline"
                >
                  {title}
                </a>
                {index < sources.length - 1 && <span>, </span>}
              </Fragment>
            ))}
          </div>
        )}
        {sources && !Array.isArray(sources) && (
          <a
            href={sources?.url}
            target="_blank"
            rel="noopener noreferrer"
            className="font-semibold underline"
          >
            {t('data-source')}
          </a>
        )}
        {extraContent}
      </PopoverContent>
    </Popover>
  );
};

TooltipButton.messages = ['components.tooltip-button'];

export default TooltipButton;
