import { FC } from 'react';

type LoadingProps = {
  message?: string;
};

const Loading: FC<LoadingProps> = ({ message }) => {
  return (
    <div className="flex flex-col gap-8 px-14 py-12 text-center md:px-10 md:py-14">
      <p className="text-xs">{message}</p>
    </div>
  );
};

export default Loading;
