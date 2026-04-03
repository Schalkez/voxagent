

export interface ProgressBarProps {
  progress: number; // 0 to 100
  label?: string;
  valueText?: string;
  colorClass?: string;
  className?: string;
  size?: 'sm' | 'md' | 'lg';
}

export const ProgressBar = ({ 
  progress, 
  label, 
  valueText, 
  colorClass = 'bg-cyan-500', 
  className,
  size = 'md'
}: ProgressBarProps) => {
  const normalizedProgress = Math.min(Math.max(progress, 0), 100);
  
  const heights = {
    sm: 'h-1',
    md: 'h-1.5',
    lg: 'h-2'
  };

  return (
    <div className={`w-full ${className || ''}`}>
      {(label || valueText) && (
        <div className="flex justify-between items-center mb-1.5">
          {label && <span className="text-[10px] text-zinc-500 uppercase tracking-widest font-bold">{label}</span>}
          {valueText && <span className="text-[10px] font-mono text-cyan-400">{valueText}</span>}
        </div>
      )}
      <div className={`w-full bg-zinc-900 rounded-full overflow-hidden ${heights[size]}`}>
        <div 
          className={`h-full ${colorClass} transition-all duration-500 ease-out`}
          style={{ width: `${normalizedProgress}%` }}
        />
      </div>
    </div>
  );
};
