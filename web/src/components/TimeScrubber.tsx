type Props = {
  min: number;
  max: number;
  value: number;
  label: string;
  onChange: (week: number) => void;
};

export function TimeScrubber({ min, max, value, label, onChange }: Props) {
  return (
    <div className="scrub">
      <label>WEEK</label>
      <input
        type="range"
        min={min}
        max={max}
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
      />
      <label>{label}</label>
    </div>
  );
}
