import { getRiskLevel, RISK_COLORS } from '../lib/risk-utils';
import { cn } from '../lib/utils';

export default function RiskBadge({ score, className }) {
  const level = getRiskLevel(score);
  const colors = RISK_COLORS[level];

  return (
    <span
      className={cn(
        'inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium',
        colors.badge,
        className
      )}
    >
      {level}
    </span>
  );
}
