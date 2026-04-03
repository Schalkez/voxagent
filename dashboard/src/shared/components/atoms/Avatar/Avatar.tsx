import { useState } from 'react';
export interface AvatarProps {
  src?: string;
  alt?: string;
  fallback?: string;
  size?: 'sm' | 'md' | 'lg' | 'xl';
  className?: string;
}

export const Avatar = ({ src, alt = "Avatar", fallback = "VA", size = 'md', className }: AvatarProps) => {
  const [imgError, setImgError] = useState(false);

  const sizes = {
    sm: 'w-6 h-6 text-[10px]',
    md: 'w-8 h-8 text-xs',
    lg: 'w-10 h-10 text-sm',
    xl: 'w-16 h-16 text-lg'
  };

  const hasImage = src && !imgError;

  return (
    <div 
      className={`
        relative rounded-full overflow-hidden flex items-center justify-center shrink-0
        bg-zinc-800 border border-zinc-700
        ${sizes[size]}
        ${className || ''}
      `}
    >
      {hasImage ? (
        <img 
          src={src} 
          alt={alt} 
          onError={() => setImgError(true)}
          className="w-full h-full object-cover"
        />
      ) : (
        <span className="font-mono font-bold text-cyan-400 capitalize">
          {fallback.substring(0, 2)}
        </span>
      )}
    </div>
  );
};
