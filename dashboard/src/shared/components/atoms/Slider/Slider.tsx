import { forwardRef, type InputHTMLAttributes } from 'react';

export interface SliderProps extends Omit<InputHTMLAttributes<HTMLInputElement>, 'type'> {
  min?: number;
  max?: number;
  step?: number;
}

export const Slider = forwardRef<HTMLInputElement, SliderProps>(
  ({ className, min = 0, max = 100, step = 1, ...props }, ref) => {
    
    // Note: Tailwind v4 handles appearance-none and accent-color beautifully,
    // but to get the specific mock styling we use custom utility layers or inline styles
    // Here we use native styling combined with pseudo elements available in standard CSS.
    // For pure utility classes without global css injection, we can style the track/thumb via custom CSS module or inline.
    
    return (
      <input
        ref={ref}
        type="range"
        min={min}
        max={max}
        step={step}
        className={`
          w-full appearance-none bg-transparent cursor-pointer
          [&::-webkit-slider-runnable-track]:h-1 
          [&::-webkit-slider-runnable-track]:bg-zinc-800 
          [&::-webkit-slider-runnable-track]:rounded-full
          [&::-webkit-slider-thumb]:appearance-none 
          [&::-webkit-slider-thumb]:h-3 
          [&::-webkit-slider-thumb]:w-3 
          [&::-webkit-slider-thumb]:rounded-full 
          [&::-webkit-slider-thumb]:bg-cyan-500 
          [&::-webkit-slider-thumb]:shadow-[0_0_10px_rgba(6,182,212,0.5)]
          [&::-webkit-slider-thumb]:-mt-1
          focus:outline-none focus:ring-0
          ${className || ''}
        `}
        {...props}
      />
    );
  }
);

Slider.displayName = 'Slider';
