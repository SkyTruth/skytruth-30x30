import { PropsWithChildren } from 'react';

const ContributionSection = ({ title, children }: PropsWithChildren<{ title: string }>) => (
  <section className="pt-6">
    <h2 className="font-mono text-xs uppercase">{title}</h2>
    {children}
  </section>
);

export default ContributionSection;
