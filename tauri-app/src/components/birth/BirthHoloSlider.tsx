import { cn } from "@/lib/utils";

interface BirthHoloSliderProps {
  label: string;
  value: number;
  min: number;
  max: number;
  step: number;
  format?: (value: number) => string;
  onChange: (value: number) => void;
  disabled?: boolean;
  className?: string;
}

export function BirthHoloSlider({
  label,
  value,
  min,
  max,
  step,
  format = (v) => String(v),
  onChange,
  disabled = false,
  className,
}: BirthHoloSliderProps) {
  const pct = ((value - min) / (max - min)) * 100;

  return (
    <div className={cn("birth-holo-slider", className)}>
      <div className="birth-holo-slider__header">
        <span className="birth-holo-slider__label">{label}</span>
        <span className="birth-holo-slider__value">{format(value)}</span>
      </div>
      <div className="birth-holo-slider__track-wrap">
        <div
          className="birth-holo-slider__fill"
          style={{ width: `${pct}%` }}
          aria-hidden
        />
        <input
          type="range"
          className="birth-holo-slider__input"
          min={min}
          max={max}
          step={step}
          value={value}
          disabled={disabled}
          onChange={(e) => onChange(Number(e.target.value))}
        />
      </div>
    </div>
  );
}
