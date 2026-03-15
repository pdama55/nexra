import type { TimeRange } from '../../types';
import { getTimeRangeLabel } from '../../hooks/useTimeRange';

const RANGES: TimeRange[] = ['last_hour', 'last_24h', 'last_7d', 'last_30d'];

interface Props {
  value: TimeRange;
  onChange: (range: TimeRange) => void;
}

export function TimeRangeSelector({ value, onChange }: Props) {
  return (
    <div style={{ display: 'flex', gap: '4px', alignItems: 'center' }}>
      {RANGES.map((range) => (
        <button
          key={range}
          className={`btn btn-sm ${range === value ? 'btn-primary' : 'btn-secondary'}`}
          onClick={() => onChange(range)}
        >
          {getTimeRangeLabel(range)}
        </button>
      ))}
    </div>
  );
}
