import React from 'react';

export interface BreadcrumbProps {
  paths: string[];
  className?: string;
}

export const Breadcrumb: React.FC<BreadcrumbProps> = ({ paths, className = '' }) => {
  return (
    <div className={`flex items-center gap-2 text-[10px] font-mono tracking-widest text-text-on-surface-variant uppercase ${className}`}>
      {paths.map((path, index) => {
        const isLast = index === paths.length - 1;
        return (
          <React.Fragment key={path}>
            <span className={isLast ? 'text-secondary-fixed-dim' : 'text-text-on-surface-variant'}>
              {path}
            </span>
            {!isLast && <span className="material-symbols-outlined text-[12px]">chevron_right</span>}
          </React.Fragment>
        );
      })}
    </div>
  );
};
