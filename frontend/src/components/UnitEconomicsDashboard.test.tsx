import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render, screen, waitFor } from '@testing-library/react';
import { getSeriesEconomics } from '../api/client.ts';
import type { SeriesEconomics } from '../types.ts';
import { UnitEconomicsDashboard } from './UnitEconomicsDashboard.tsx';

vi.mock('../api/client.ts', () => ({
  getSeriesEconomics: vi.fn(),
}));

const baseEconomics: SeriesEconomics = {
  series_id: 'series-1',
  total_actual_cost: '4.75',
  generation_count: 4,
  episode_count: 2,
  average_cost_per_generation: '1.1875',
  cost_by_generation_type: [
    { value: 'IMAGE', total_cost: '2', generation_count: 2 },
    { value: 'VIDEO', total_cost: '2.5', generation_count: 1 },
    { value: 'TTS', total_cost: '0.25', generation_count: 1 },
  ],
  cost_by_provider: [{ value: 'fake', total_cost: '4.75', generation_count: 4 }],
  cost_by_model: [
    { value: 'fake-image', total_cost: '2', generation_count: 2 },
    { value: 'fake-video', total_cost: '2.5', generation_count: 1 },
    { value: 'fake-tts', total_cost: '0.25', generation_count: 1 },
  ],
  total_configured_budget: '100',
  total_actual_spend: '4.75',
  total_reserved: '0',
  total_remaining_budget: '95.25',
  budget_utilization: '0.0475',
  budget_currency: 'USD',
  episode_summaries: [
    {
      episode_id: 'ep-1',
      title: 'Episode 1',
      actual_spend: '4',
      generation_count: 2,
      budget_amount: '50',
      budget_currency: 'USD',
      budget_status: 'WITHIN_BUDGET',
      remaining_budget: '46',
      utilization: '0.08',
    },
    {
      episode_id: 'ep-2',
      title: 'Episode 2',
      actual_spend: '0.75',
      generation_count: 2,
      budget_amount: '50',
      budget_currency: 'USD',
      budget_status: 'WITHIN_BUDGET',
      remaining_budget: '49.25',
      utilization: '0.015',
    },
  ],
};

afterEach(() => {
  cleanup();
  vi.resetAllMocks();
});

beforeEach(() => {
  vi.mocked(getSeriesEconomics).mockReset();
});

describe('UnitEconomicsDashboard', () => {
  it('renders loading state initially', () => {
    vi.mocked(getSeriesEconomics).mockImplementation(() => new Promise(() => {}));
    render(<UnitEconomicsDashboard seriesId="series-1" />);
    expect(screen.getByText('Loading…')).not.toBeNull();
  });

  it('renders dashboard metrics after load', async () => {
    vi.mocked(getSeriesEconomics).mockResolvedValue(baseEconomics);
    render(<UnitEconomicsDashboard seriesId="series-1" />);
    await waitFor(() => expect(screen.getByText('Total Spend')).not.toBeNull());
    expect(screen.getAllByText('4.75').length).toBeGreaterThan(0);
    expect(screen.getByText('Generation Count')).not.toBeNull();
    expect(screen.getAllByText('4').length).toBeGreaterThan(0);
    expect(screen.getByText('Episode 1')).not.toBeNull();
    expect(screen.getByText('IMAGE')).not.toBeNull();
  });

  it('renders error state on API failure', async () => {
    vi.mocked(getSeriesEconomics).mockRejectedValue(new Error('Network error'));
    render(<UnitEconomicsDashboard seriesId="series-1" />);
    await waitFor(() => expect(screen.getByText('Network error')).not.toBeNull());
  });

  it('renders empty state for no generation data', async () => {
    vi.mocked(getSeriesEconomics).mockResolvedValue({
      ...baseEconomics,
      total_actual_cost: '0',
      generation_count: 0,
      episode_count: 0,
      cost_by_generation_type: [],
      cost_by_provider: [],
      cost_by_model: [],
      total_actual_spend: '0',
      total_remaining_budget: '100',
      budget_utilization: '0',
      episode_summaries: [
        {
          episode_id: 'ep-1',
          title: 'Episode 1',
          actual_spend: '0',
          generation_count: 0,
          budget_amount: '50',
          budget_currency: 'USD',
          budget_status: 'WITHIN_BUDGET',
          remaining_budget: '50',
          utilization: '0',
        },
      ],
    });
    render(<UnitEconomicsDashboard seriesId="series-1" />);
    await waitFor(() =>
      expect(screen.getByText('No generation cost data yet for this series.')).not.toBeNull()
    );
    expect(screen.getByText('Total Spend')).not.toBeNull();
  });

  it('renders no-budget note', async () => {
    vi.mocked(getSeriesEconomics).mockResolvedValue({
      ...baseEconomics,
      total_configured_budget: '0',
      total_remaining_budget: '0',
      budget_utilization: '0',
    });
    render(<UnitEconomicsDashboard seriesId="series-1" />);
    await waitFor(() => expect(screen.getByText('No budget configured')).not.toBeNull());
  });
});
