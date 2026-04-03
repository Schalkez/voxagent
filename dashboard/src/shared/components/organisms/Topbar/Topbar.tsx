import React from 'react';
import { Breadcrumb } from '@shared/components';
import { Button } from '@shared/components';

export interface TopbarProps {
  paths: string[];
  actionNode?: React.ReactNode;
}

export const Topbar: React.FC<TopbarProps> = ({ paths, actionNode }) => {
  return (
    <header className="h-20 px-8 flex items-center justify-between border-b border-outline-variant/20 bg-surface-base/50 backdrop-blur-md sticky top-0 z-10">
      <Breadcrumb paths={paths} />
      {actionNode || (
        <Button variant="secondary" className="scale-90 origin-right">
          Mute Microphone
        </Button>
      )}
    </header>
  );
};
