import { useCallback } from 'react';

import { useTranslations } from 'next-intl';

import { FCWithMessages } from '@/types';

const ModellingIntro: FCWithMessages = () => {
  const t = useTranslations('containers.map-sidebar-main-panel');

  const parseTextWithStyle = useCallback(
    (textKey, className: string) => {
      return t.rich(textKey, {
        b: (chunks) => <span className={className}>{chunks}</span>,
      });
    },
    [t]
  );

  return (
    <div className="flex flex-col gap-4 px-4 py-4 md:px-8">
      <span className="text-xl/[1.5rem] font-bold">
        {parseTextWithStyle('draw-upload-directions', 'text-blue-600')}
      </span>
      {parseTextWithStyle('draw-area', 'text-blue-600 font-bold text-lg')}
      <ol className="flex flex-col gap-[0.625rem]">
        <li className="flex items-start">
          <p className="mr-[1rem] font-mono text-[1rem]">01</p>
          <p>{parseTextWithStyle('draw-step-1-description', 'font-bold text-[1rem]')}</p>
        </li>

        <li className="flex items-start gap-[0.625rem]">
          <p className="mr-[1rem] font-mono text-[1.125rem]">02</p>
          <p>{t('draw-step-2-description')}</p>
        </li>

        <li className="flex items-start gap-[0.625rem]">
          <p className="mr-[1rem] font-mono text-[1.125rem]">03</p>
          <p>{t('draw-step-3-description')}</p>
        </li>
      </ol>

      {parseTextWithStyle('upload-area', 'text-blue-600 font-bold text-lg')}
      <ol className="flex flex-col gap-[0.625rem]">
        <li className="flex items-start gap-[0.625rem]">
          <p className="mr-[1rem] font-mono text-[1.125rem]">01</p>
          <p>{parseTextWithStyle('upload-step-1-description', 'font-bold')}</p>
        </li>

        <li className="flex items-start gap-[0.625rem]">
          <p className="mr-[1rem] font-mono text-[1.125rem]">02</p>
          <p>{t('upload-step-2-description')}</p>
        </li>
      </ol>

      <p>{t('upload-context-layers')}</p>
    </div>
  );
};

ModellingIntro.messages = ['containers.map-sidebar-main-panel'];

export default ModellingIntro;
