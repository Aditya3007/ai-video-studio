import { useCallback, useEffect, useState } from 'react';
import { getSeriesEconomics } from '../api/client.ts';
import type { SeriesEconomics } from '../types.ts';
import { Empty, ErrorMessage, Loading } from './Status.tsx';
import './UnitEconomicsDashboard.css';

interface UnitEconomicsDashboardProps {
  seriesId: string;
}

export function UnitEconomicsDashboard({ seriesId }: UnitEconomicsDashboardProps) {
  const [data, setData] = useState<SeriesEconomics | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await getSeriesEconomics(seriesId);
      setData(result);
    } catch (err) {
      setData(null);
      setError(err instanceof Error ? err.message : 'Failed to load unit economics');
    } finally {
      setLoading(false);
    }
  }, [seriesId]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    load();
  }, [load]);

  if (loading) return <Loading />;
  if (error) return <ErrorMessage message={error} />;
  if (!data) return <Empty message="No economics data available." />;

  const hasData = data.generation_count > 0;
  const noBudget = data.total_configured_budget === '0' || data.total_configured_budget === '0.0';

  return (
    <div className="unit-economics">
      <header className="economics-header">
        <h2>Unit Economics</h2>
        <p className="economics-note">Production cost analytics — revenue model not configured.</p>
      </header>

      <section className="economics-summary">
        <div className="metric-card">
          <span className="metric-label">Total Spend</span>
          <span className="metric-value">{data.total_actual_cost}</span>
          <span className="metric-currency">{data.budget_currency || 'USD'}</span>
        </div>
        <div className="metric-card">
          <span className="metric-label">Generation Count</span>
          <span className="metric-value">{data.generation_count}</span>
        </div>
        <div className="metric-card">
          <span className="metric-label">Configured Budget</span>
          <span className="metric-value">{data.total_configured_budget}</span>
          {noBudget && <span className="metric-note">No budget configured</span>}
        </div>
        <div className="metric-card">
          <span className="metric-label">Remaining Budget</span>
          <span className="metric-value">{data.total_remaining_budget}</span>
        </div>
        <div className="metric-card">
          <span className="metric-label">Utilization</span>
          <span className="metric-value">{data.budget_utilization}</span>
        </div>
      </section>

      {!hasData && <Empty message="No generation cost data yet for this series." />}

      {hasData && (
        <>
          <section className="economics-breakdown">
            <h3>Cost by Generation Type</h3>
            <BreakdownList items={data.cost_by_generation_type} />
          </section>

          <section className="economics-breakdown">
            <h3>Cost by Provider</h3>
            <BreakdownList items={data.cost_by_provider} />
          </section>

          <section className="economics-breakdown">
            <h3>Cost by Model</h3>
            <BreakdownList items={data.cost_by_model} />
          </section>

          <section className="economics-episodes">
            <h3>Episode Breakdown</h3>
            {data.episode_summaries.length === 0 ? (
              <Empty message="No episodes in this series." />
            ) : (
              <table className="episodes-table">
                <thead>
                  <tr>
                    <th>Episode</th>
                    <th>Spend</th>
                    <th>Generations</th>
                    <th>Budget</th>
                    <th>Remaining</th>
                    <th>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {data.episode_summaries.map((ep) => (
                    <tr key={ep.episode_id}>
                      <td>{ep.title}</td>
                      <td>{ep.actual_spend}</td>
                      <td>{ep.generation_count}</td>
                      <td>{ep.budget_amount ?? '-'}</td>
                      <td>{ep.remaining_budget ?? '-'}</td>
                      <td>{ep.budget_status}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </section>
        </>
      )}
    </div>
  );
}

function BreakdownList({
  items,
}: {
  items: { value: string; total_cost: string; generation_count: number }[];
}) {
  if (items.length === 0) {
    return <p className="empty">No data.</p>;
  }
  return (
    <ul className="breakdown-list">
      {items.map((item) => (
        <li key={item.value} className="breakdown-item">
          <span className="breakdown-value">{item.value}</span>
          <span className="breakdown-cost">{item.total_cost}</span>
          <span className="breakdown-count">{item.generation_count} generation(s)</span>
        </li>
      ))}
    </ul>
  );
}
