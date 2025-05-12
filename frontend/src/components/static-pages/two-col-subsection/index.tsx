import { PropsWithChildren, ReactNode } from 'react';

import {
  SubSectionTitle,
  SubSectionDescription,
  SubSectionContent,
} from '@/components/static-pages/sub-section';

export type TwoColSubSection = PropsWithChildren<{
  title: string;
  description?: string | ReactNode;
  itemNum?: number;
  itemTotal?: number;
}>;

const TwoColSubSection: React.FC<TwoColSubSection> = ({
  title,
  description,
  itemNum,
  itemTotal,
  children,
}) => {
  const minTwoDigits = (number: number) => {
    return (number < 10 ? '0' : '') + number;
  };

  const isNumbered = itemNum && itemTotal ? true : false;

  return (
    <div className="mt-0 flex flex-col gap-8 md:mt-20 md:flex-row">
      <div className="flex w-full flex-col pt-5 md:w-[50%]">
        {isNumbered && (
          <span className="mb-2 font-mono text-xl md:mb-6">
            <span className="text-black">{minTwoDigits(itemNum)}</span>
            <span className="opacity-60">-{minTwoDigits(itemTotal)}</span>
          </span>
        )}
        <div className="border-t border-black md:pt-3.5">
          <SubSectionTitle>{title}</SubSectionTitle>
          {description && <SubSectionDescription>{description}</SubSectionDescription>}
        </div>
      </div>
      <SubSectionContent isNumbered={isNumbered}>{children}</SubSectionContent>
    </div>
  );
};

export default TwoColSubSection;
